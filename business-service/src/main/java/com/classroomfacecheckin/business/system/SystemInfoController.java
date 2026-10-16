package com.classroomfacecheckin.business.system;

import com.classroomfacecheckin.business.api.ApiResponse;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/system")
public class SystemInfoController {

    @GetMapping("/info")
    public ApiResponse<Map<String, String>> info() {
        return ApiResponse.success(Map.of(
                "service", "classroom-face-checkin-business-service",
                "version", "v1"));
    }
}
