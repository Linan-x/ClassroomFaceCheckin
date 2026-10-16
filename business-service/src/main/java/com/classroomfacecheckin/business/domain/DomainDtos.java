package com.classroomfacecheckin.business.domain;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.List;

record ClassroomRequest(@NotBlank @Size(max = 64) String code, @NotBlank @Size(max = 128) String name, @Size(max = 500) String description) {}
record StudentRequest(@NotBlank @Size(max = 64) String studentNumber, @NotBlank @Size(max = 128) String fullName, Long classroomId, @Size(max = 64) String phone) {}
record CourseRequest(@NotBlank @Size(max = 64) String code, @NotBlank @Size(max = 128) String name, @Size(max = 500) String description) {}
record PhotoMetadataRequest(@NotBlank @Size(max = 512) @Pattern(regexp = "^(legacy|storage)://.*$", message = "storageUri must use a non-public legacy:// or storage:// reference") String storageUri, @Size(max = 128) String contentHash, boolean primary) {}
record IdsRequest(@NotNull List<Long> ids) {}
record SessionRequest(@NotBlank @Size(max = 128) String name, Instant startsAt) {}
record ClassroomDto(Long id, String code, String name, String description) {}
record StudentDto(Long id, String studentNumber, String fullName, Long classroomId, String phone) {}
record CourseDto(Long id, String code, String name, String description, List<Long> classroomIds) {}
record PhotoDto(Long id, String storageUri, String contentHash, boolean primary) {}
record EnrollmentDto(Long id, Long studentId) {}
record CheckinSessionDto(Long id, Long courseId, String name, String status, Instant startsAt, Instant endsAt) {}
