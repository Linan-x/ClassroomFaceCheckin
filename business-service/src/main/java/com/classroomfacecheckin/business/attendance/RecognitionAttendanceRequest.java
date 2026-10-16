package com.classroomfacecheckin.business.attendance;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record RecognitionAttendanceRequest(
        @NotBlank @Size(max = 64) @Pattern(regexp = "^[A-Za-z0-9_-]+$") String facebankId,
        @NotBlank @Size(max = 7_000_000) String imageBase64) {
}
