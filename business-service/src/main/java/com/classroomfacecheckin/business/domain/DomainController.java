package com.classroomfacecheckin.business.domain;

import com.classroomfacecheckin.business.api.ApiResponse;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1")
public class DomainController {
    private final DomainService service;
    public DomainController(DomainService service) { this.service = service; }

    @GetMapping("/classrooms") public ApiResponse<List<ClassroomDto>> classrooms() { return ApiResponse.success(service.classrooms()); }
    @PostMapping("/classrooms") public ResponseEntity<ApiResponse<ClassroomDto>> createClassroom(@Valid @RequestBody ClassroomRequest request) {
        ClassroomDto item = service.createClassroom(request); return created("/api/v1/classrooms/" + item.id(), item);
    }
    @PutMapping("/classrooms/{id}") public ApiResponse<ClassroomDto> updateClassroom(@PathVariable Long id, @Valid @RequestBody ClassroomRequest request) { return ApiResponse.success(service.updateClassroom(id, request)); }

    @GetMapping("/students") public ApiResponse<List<StudentDto>> students() { return ApiResponse.success(service.students()); }
    @PostMapping("/students") public ResponseEntity<ApiResponse<StudentDto>> createStudent(@Valid @RequestBody StudentRequest request) {
        StudentDto item = service.createStudent(request); return created("/api/v1/students/" + item.id(), item);
    }
    @PutMapping("/students/{id}") public ApiResponse<StudentDto> updateStudent(@PathVariable Long id, @Valid @RequestBody StudentRequest request) { return ApiResponse.success(service.updateStudent(id, request)); }
    @PostMapping("/students/{id}/photos") public ResponseEntity<ApiResponse<PhotoDto>> addPhoto(@PathVariable Long id, @Valid @RequestBody PhotoMetadataRequest request) {
        PhotoDto item = service.addPhoto(id, request); return created("/api/v1/students/" + id + "/photos/" + item.id(), item);
    }

    @GetMapping("/courses") public ApiResponse<List<CourseDto>> courses() { return ApiResponse.success(service.courses()); }
    @PostMapping("/courses") public ResponseEntity<ApiResponse<CourseDto>> createCourse(@Valid @RequestBody CourseRequest request) {
        CourseDto item = service.createCourse(request); return created("/api/v1/courses/" + item.id(), item);
    }
    @PutMapping("/courses/{id}") public ApiResponse<CourseDto> updateCourse(@PathVariable Long id, @Valid @RequestBody CourseRequest request) { return ApiResponse.success(service.updateCourse(id, request)); }
    @PutMapping("/courses/{id}/classrooms") public ApiResponse<CourseDto> setClassrooms(@PathVariable Long id, @Valid @RequestBody IdsRequest request) { return ApiResponse.success(service.setCourseClassrooms(id, request)); }
    @GetMapping("/courses/{id}/enrollments") public ApiResponse<List<EnrollmentDto>> enrollments(@PathVariable Long id) { return ApiResponse.success(service.enrollments(id)); }
    @PutMapping("/courses/{courseId}/students/{studentId}") public ResponseEntity<ApiResponse<EnrollmentDto>> enroll(@PathVariable Long courseId, @PathVariable Long studentId) {
        EnrollmentDto item = service.enroll(courseId, studentId); return ResponseEntity.status(201).body(ApiResponse.success(item));
    }
    @DeleteMapping("/courses/{courseId}/students/{studentId}") public ResponseEntity<Void> unenroll(@PathVariable Long courseId, @PathVariable Long studentId) { service.unenroll(courseId, studentId); return ResponseEntity.noContent().build(); }
    @GetMapping("/courses/{id}/checkin-sessions") public ApiResponse<List<CheckinSessionDto>> sessions(@PathVariable Long id) { return ApiResponse.success(service.sessions(id)); }
    @PostMapping("/courses/{id}/checkin-sessions") public ResponseEntity<ApiResponse<CheckinSessionDto>> createSession(@PathVariable Long id, @Valid @RequestBody SessionRequest request) {
        CheckinSessionDto item = service.createSession(id, request); return created("/api/v1/checkin-sessions/" + item.id(), item);
    }
    @PostMapping("/checkin-sessions/{id}/end") public ApiResponse<CheckinSessionDto> endSession(@PathVariable Long id) { return ApiResponse.success(service.endSession(id)); }

    private <T> ResponseEntity<ApiResponse<T>> created(String location, T item) { return ResponseEntity.created(URI.create(location)).body(ApiResponse.success(item)); }
}
