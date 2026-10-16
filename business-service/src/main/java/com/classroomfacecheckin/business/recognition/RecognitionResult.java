package com.classroomfacecheckin.business.recognition;

public record RecognitionResult(Long studentId, Double confidence) {
    public boolean matched() {
        return studentId != null && confidence != null;
    }
}
