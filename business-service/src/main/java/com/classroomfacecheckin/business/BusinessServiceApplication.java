package com.classroomfacecheckin.business;

import com.classroomfacecheckin.business.compatibility.CompatibilityProperties;
import com.classroomfacecheckin.business.realtime.RealtimeProperties;
import com.classroomfacecheckin.business.recognition.RecognitionProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@EnableConfigurationProperties({RecognitionProperties.class, CompatibilityProperties.class, RealtimeProperties.class})
public class BusinessServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(BusinessServiceApplication.class, args);
    }
}
