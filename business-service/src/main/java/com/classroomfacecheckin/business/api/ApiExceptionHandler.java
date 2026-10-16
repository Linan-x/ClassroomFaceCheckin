package com.classroomfacecheckin.business.api;

import com.classroomfacecheckin.business.recognition.RecognitionRejectedException;
import com.classroomfacecheckin.business.recognition.RecognitionUnavailableException;
import jakarta.validation.ConstraintViolationException;
import org.springframework.http.ResponseEntity;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler({
            ConstraintViolationException.class,
            MethodArgumentNotValidException.class,
            HttpMessageNotReadableException.class,
            MethodArgumentTypeMismatchException.class,
            IllegalArgumentException.class
    })
    public ResponseEntity<ApiResponse<Void>> handleBadRequest(Exception exception) {
        return ResponseEntity.badRequest()
                .body(ApiResponse.failure("VALIDATION_ERROR", "Request validation failed."));
    }

    @ExceptionHandler(NotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNotFound(NotFoundException exception) {
        return ResponseEntity.status(404)
                .body(ApiResponse.failure("NOT_FOUND", exception.getMessage()));
    }

    @ExceptionHandler({ConflictException.class, DataIntegrityViolationException.class})
    public ResponseEntity<ApiResponse<Void>> handleConflict(Exception exception) {
        return ResponseEntity.status(409)
                .body(ApiResponse.failure("CONFLICT", exception.getMessage()));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<ApiResponse<Void>> handleInvalidState(IllegalStateException exception) {
        return ResponseEntity.status(409)
                .body(ApiResponse.failure("INVALID_STATE", exception.getMessage()));
    }

    @ExceptionHandler(RecognitionRejectedException.class)
    public ResponseEntity<ApiResponse<Void>> handleRecognitionRejected(RecognitionRejectedException exception) {
        return ResponseEntity.unprocessableEntity()
                .body(ApiResponse.failure("RECOGNITION_REJECTED", exception.getMessage()));
    }

    @ExceptionHandler(RecognitionUnavailableException.class)
    public ResponseEntity<ApiResponse<Void>> handleRecognitionUnavailable(RecognitionUnavailableException exception) {
        return ResponseEntity.status(503)
                .body(ApiResponse.failure("RECOGNITION_UNAVAILABLE", exception.getMessage()));
    }
}
