"""
Fixed Queue Processing System for SAP Anvil Tool

This module implements a proper worker-based queue system with fixes for:
- Infinite polling loop issues
- Binary data serialization problems
- Queue position calculation errors
- Missing timeout protections
- Enhanced error handling
"""

import threading
import time
import uuid
import logging
import json
import base64
from queue import Queue, Empty
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import traceback


class JobStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ProcessingJob:
    job_id: str
    job_type: str  # 'preview' or 'highres'
    params: Dict[str, Any]
    status: JobStatus = JobStatus.QUEUED
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class ImageProcessor:
    """
    Worker-based image processing queue system.
    
    This replaces the fake queue system with actual background workers
    that process jobs independently of Flask request threads.
    """
    
    def __init__(self, num_workers: int = 2, result_ttl: int = 3600):
        """
        Initialize the image processor with worker threads.
        
        Args:
            num_workers: Number of background worker threads
            result_ttl: Time to live for job results in seconds (default 1 hour)
        """
        # Setup logging first
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        self.num_workers = num_workers
        self.result_ttl = result_ttl
        
        # Thread-safe queue for jobs
        self.job_queue = Queue()
        
        # Thread-safe storage for job results and status
        self.jobs_lock = threading.RLock()
        self.jobs: Dict[str, ProcessingJob] = {}
        
        # Worker threads
        self.workers = []
        self.shutdown_event = threading.Event()
        
        # Job processors mapping
        self.job_processors: Dict[str, Callable] = {}
        
        # Start worker threads
        self._start_workers()
        
        # Start cleanup thread
        self._start_cleanup_thread()
    
    def _start_workers(self):
        """Start background worker threads."""
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f'ImageWorker-{i}',
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            self.logger.info(f"Started worker thread: ImageWorker-{i}")
    
    def _start_cleanup_thread(self):
        """Start cleanup thread for expired job results."""
        cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name='JobCleanup',
            daemon=True
        )
        cleanup_thread.start()
        self.logger.info("Started job cleanup thread")
    
    def register_processor(self, job_type: str, processor_func: Callable):
        """
        Register a job processor function for a specific job type.
        
        Args:
            job_type: Type of job (e.g., 'preview', 'highres')
            processor_func: Function that processes the job
        """
        self.job_processors[job_type] = processor_func
        self.logger.info(f"Registered processor for job type: {job_type}")
    
    def submit_job(self, job_type: str, params: Dict[str, Any]) -> str:
        """
        Submit a new job to the processing queue.
        
        Args:
            job_type: Type of job to process
            params: Parameters for the job
            
        Returns:
            Unique job ID for tracking
        """
        job_id = uuid.uuid4().hex
        job = ProcessingJob(
            job_id=job_id,
            job_type=job_type,
            params=params
        )
        
        with self.jobs_lock:
            self.jobs[job_id] = job
        
        # Add to processing queue
        self.job_queue.put(job)
        
        self.logger.info(f"Submitted job {job_id} of type {job_type}")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a job.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Dictionary with job status information or None if not found
        """
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return None
            
            # Prepare result based on job status
            result = None
            if job.status == JobStatus.COMPLETED and job.result:
                # Make sure result is JSON serializable
                if isinstance(job.result, dict):
                    result = job.result
                elif isinstance(job.result, bytes):
                    # Convert bytes to base64 for JSON serialization
                    result = {
                        'type': 'binary',
                        'data': base64.b64encode(job.result).decode('utf-8')
                    }
                else:
                    result = str(job.result)
            
            return {
                'job_id': job.job_id,
                'status': job.status.value,
                'created_at': job.created_at,
                'started_at': job.started_at,
                'completed_at': job.completed_at,
                'result': result,
                'error': job.error,
                'position': self._get_queue_position(job_id)
            }
    
    def get_queue_position(self, job_id: str) -> int:
        """
        Get the position of a job in the queue.
        
        Args:
            job_id: Unique job identifier
            
        Returns:
            Position in queue (1-based), or 0 if not queued/being processed, or -1 if not found
        """
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if not job:
                return -1
            
            if job.status != JobStatus.QUEUED:
                return 0  # Job is being processed or completed
            
            # Count queued jobs created before this one
            position = 1
            for other_job in self.jobs.values():
                if (other_job.status == JobStatus.QUEUED and 
                    other_job.created_at < job.created_at):
                    position += 1
            
            return position
    
    def _get_queue_position(self, job_id: str) -> int:
        """Internal method to get queue position."""
        return self.get_queue_position(job_id)
    
    def _worker_loop(self):
        """Main worker loop that processes jobs from the queue."""
        worker_name = threading.current_thread().name
        self.logger.info(f"Worker {worker_name} started")
        
        while not self.shutdown_event.is_set():
            try:
                # Get job from queue with timeout
                job = self.job_queue.get(timeout=1)
                
                self.logger.info(f"Worker {worker_name} processing job {job.job_id}")
                
                # Update job status to processing
                with self.jobs_lock:
                    if job.job_id in self.jobs:
                        self.jobs[job.job_id].status = JobStatus.PROCESSING
                        self.jobs[job.job_id].started_at = time.time()
                
                # Process the job
                try:
                    processor = self.job_processors.get(job.job_type)
                    if not processor:
                        raise ValueError(f"No processor registered for job type: {job.job_type}")
                    
                    # Execute the processor
                    result = processor(job.params)
                    
                    # Mark job as completed
                    with self.jobs_lock:
                        if job.job_id in self.jobs:
                            self.jobs[job.job_id].status = JobStatus.COMPLETED
                            self.jobs[job.job_id].result = result
                            self.jobs[job.job_id].completed_at = time.time()
                    
                    self.logger.info(f"Job {job.job_id} completed successfully")
                
                except Exception as e:
                    # Mark job as failed
                    error_msg = f"Job processing failed: {str(e)}"
                    self.logger.error(f"Job {job.job_id} failed: {error_msg}")
                    self.logger.error(traceback.format_exc())
                    
                    with self.jobs_lock:
                        if job.job_id in self.jobs:
                            self.jobs[job.job_id].status = JobStatus.FAILED
                            self.jobs[job.job_id].error = error_msg
                            self.jobs[job.job_id].completed_at = time.time()
                
                finally:
                    # Mark task as done
                    self.job_queue.task_done()
            
            except Empty:
                # Timeout waiting for job - continue loop
                continue
            except Exception as e:
                self.logger.error(f"Worker {worker_name} error: {e}")
                self.logger.error(traceback.format_exc())
        
        self.logger.info(f"Worker {worker_name} stopped")
    
    def _cleanup_loop(self):
        """Cleanup loop that removes expired job results."""
        self.logger.info("Job cleanup thread started")
        
        while not self.shutdown_event.is_set():
            try:
                current_time = time.time()
                expired_jobs = []
                
                with self.jobs_lock:
                    for job_id, job in self.jobs.items():
                        # Only clean up completed or failed jobs
                        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                            if job.completed_at and (current_time - job.completed_at) > self.result_ttl:
                                expired_jobs.append(job_id)
                    
                    # Remove expired jobs
                    for job_id in expired_jobs:
                        del self.jobs[job_id]
                        self.logger.info(f"Cleaned up expired job: {job_id}")
                
                # Sleep for 5 minutes between cleanup cycles
                time.sleep(300)
                
            except Exception as e:
                self.logger.error(f"Cleanup thread error: {e}")
                time.sleep(60)  # Wait a minute before retrying
        
        self.logger.info("Job cleanup thread stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the queue system.
        
        Returns:
            Dictionary with queue statistics
        """
        with self.jobs_lock:
            queued_count = sum(1 for job in self.jobs.values() if job.status == JobStatus.QUEUED)
            processing_count = sum(1 for job in self.jobs.values() if job.status == JobStatus.PROCESSING)
            completed_count = sum(1 for job in self.jobs.values() if job.status == JobStatus.COMPLETED)
            failed_count = sum(1 for job in self.jobs.values() if job.status == JobStatus.FAILED)
            
            # Get list of pending jobs for admin panel
            pending_jobs = []
            for job in self.jobs.values():
                if job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
                    pending_jobs.append({
                        'job_id': job.job_id,
                        'type': job.job_type,
                        'status': job.status.value,
                        'created_at': job.created_at
                    })
            
            return {
                'workers': len(self.workers),
                'queue_size': self.job_queue.qsize(),
                'total_jobs': len(self.jobs),
                'queued': queued_count,
                'processing': processing_count,
                'completed': completed_count,
                'failed': failed_count,
                'pending_jobs': pending_jobs
            }
    
    def shutdown(self):
        """Gracefully shutdown the processor and all worker threads."""
        self.logger.info("Shutting down image processor...")
        self.shutdown_event.set()
        
        # Wait for all workers to finish
        for worker in self.workers:
            worker.join(timeout=5.0)
        
        self.logger.info("Image processor shutdown complete")


# Global processor instance
_processor: Optional[ImageProcessor] = None


def get_processor() -> ImageProcessor:
    """Get the global image processor instance."""
    global _processor
    if _processor is None:
        _processor = ImageProcessor(num_workers=2)
    return _processor


def initialize_processor(num_workers: int = 2, result_ttl: int = 3600) -> ImageProcessor:
    """
    Initialize the global image processor with custom settings.
    
    Args:
        num_workers: Number of worker threads
        result_ttl: Result time-to-live in seconds
        
    Returns:
        The initialized processor instance
    """
    global _processor
    if _processor is not None:
        _processor.shutdown()
    
    _processor = ImageProcessor(num_workers=num_workers, result_ttl=result_ttl)
    return _processor
