package com.classroomfacecheckin.business.recognition;

public interface RecognitionClient {
    RecognitionResult recognize(String facebankId, String imageBase64, String requestId);
}
