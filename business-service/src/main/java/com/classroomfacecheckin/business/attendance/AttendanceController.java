package com.classroomfacecheckin.business.attendance;

import com.classroomfacecheckin.business.api.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/checkin-sessions")
public class AttendanceController {
    private final AttendanceService service;

    public AttendanceController(AttendanceService service) {
        this.service = service;
    }

    @PostMapping("/{id}/attendance/recognize")
    public ApiResponse<AttendanceResponse> recognize(
            @PathVariable Long id,
            @Valid @RequestBody RecognitionAttendanceRequest request,
            HttpServletRequest servletRequest) {
        String requestId = servletRequest.getHeader("X-Request-ID");
        if (requestId == null || requestId.isBlank() || requestId.length() > 128) {
            requestId = UUID.randomUUID().toString();
        }
        return ApiResponse.success(service.recognizeAndRecord(id, request, requestId));
    }
}
