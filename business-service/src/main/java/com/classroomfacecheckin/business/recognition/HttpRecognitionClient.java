package com.classroomfacecheckin.business.recognition;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.net.URI;
import java.time.Duration;
import java.util.Map;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientResponseException;

@Component
public class HttpRecognitionClient implements RecognitionClient {
    private final RecognitionProperties properties;
    private final RestClient client;

    public HttpRecognitionClient(RecognitionProperties properties) {
        this.properties = properties;
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofMillis(properties.connectTimeoutMs()));
        factory.setReadTimeout(Duration.ofMillis(properties.readTimeoutMs()));
        this.client = RestClient.builder().requestFactory(factory).build();
    }

    @Override
    public RecognitionResult recognize(String facebankId, String imageBase64, String requestId) {
        if (!properties.enabled()) {
            throw new RecognitionUnavailableException("Recognition integration is disabled.");
        }
        if (properties.baseUrl() == null || properties.sharedToken() == null || properties.sharedToken().isBlank()) {
            throw new RecognitionUnavailableException("Recognition integration is not configured.");
        }
        try {
            RecognitionResponse response = client.post()
                    .uri(resolve("/internal/v1/recognitions"))
                    .header("Authorization", "Bearer " + properties.sharedToken())
                    .header("X-Request-ID", requestId)
                    .body(Map.of("facebank_id", facebankId, "image_base64", imageBase64))
                    .retrieve()
                    .body(RecognitionResponse.class);
            if (response == null || response.result() == null) {
                throw new RecognitionUnavailableException("Recognition service returned an invalid response.");
            }
            return new RecognitionResult(response.result().recognizedStudentId(), response.result().confidence());
        } catch (RestClientResponseException exception) {
            if (exception.getStatusCode().is4xxClientError()) {
                throw new RecognitionRejectedException("Recognition request was rejected.");
            }
            throw new RecognitionUnavailableException("Recognition service failed.");
        } catch (ResourceAccessException exception) {
            throw new RecognitionUnavailableException("Recognition service is unavailable.");
        }
    }

    private URI resolve(String path) {
        return properties.baseUrl().resolve(path);
    }

    private record RecognitionResponse(RecognitionPayload result) {
    }

    private record RecognitionPayload(
            String status,
            @JsonProperty("recognized_student_id") Long recognizedStudentId,
            Double confidence) {
    }
}
