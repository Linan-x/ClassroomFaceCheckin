package com.classroomfacecheckin.business.domain;

import com.classroomfacecheckin.business.api.ConflictException;
import com.classroomfacecheckin.business.api.NotFoundException;
import java.util.List;
import java.util.LinkedHashSet;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional
public class DomainService {
    private final ClassroomRepository classrooms; private final StudentRepository students; private final StudentPhotoRepository photos;
    private final CourseRepository courses; private final EnrollmentRepository enrollments; private final CheckinSessionRepository sessions;
    public DomainService(ClassroomRepository classrooms, StudentRepository students, StudentPhotoRepository photos, CourseRepository courses, EnrollmentRepository enrollments, CheckinSessionRepository sessions) {
        this.classrooms = classrooms; this.students = students; this.photos = photos; this.courses = courses; this.enrollments = enrollments; this.sessions = sessions;
    }
    @Transactional(readOnly = true) public List<ClassroomDto> classrooms() { return classrooms.findAll().stream().map(this::classroom).toList(); }
    public ClassroomDto createClassroom(ClassroomRequest request) { return classroom(save(() -> classrooms.save(new Classroom(request.code(), request.name(), request.description())))); }
    public ClassroomDto updateClassroom(Long id, ClassroomRequest request) { Classroom item = classroomEntity(id); item.update(request.code(), request.name(), request.description()); return classroom(save(() -> classrooms.save(item))); }
    @Transactional(readOnly = true) public List<StudentDto> students() { return students.findAll().stream().map(this::student).toList(); }
    public StudentDto createStudent(StudentRequest request) { return student(save(() -> students.save(new Student(request.studentNumber(), request.fullName(), classroomOrNull(request.classroomId()), request.phone())))); }
    public StudentDto updateStudent(Long id, StudentRequest request) { Student item = studentEntity(id); item.update(request.studentNumber(), request.fullName(), classroomOrNull(request.classroomId()), request.phone()); return student(save(() -> students.save(item))); }
    public PhotoDto addPhoto(Long studentId, PhotoMetadataRequest request) {
        if (request.storageUri().contains("..")) throw new IllegalArgumentException("Photo references must not contain parent paths.");
        Student student = studentEntity(studentId);
        StudentPhoto existing = photos.findByStudentIdAndStorageUri(studentId, request.storageUri()).orElse(null);
        return photo(existing == null ? photos.save(new StudentPhoto(student, request.storageUri(), request.contentHash(), request.primary())) : existing);
    }
    @Transactional(readOnly = true) public List<CourseDto> courses() { return courses.findAll().stream().map(this::course).toList(); }
    public CourseDto createCourse(CourseRequest request) { return course(save(() -> courses.save(new Course(request.code(), request.name(), request.description())))); }
    public CourseDto updateCourse(Long id, CourseRequest request) { Course item = courseEntity(id); item.update(request.code(), request.name(), request.description()); return course(save(() -> courses.save(item))); }
    public CourseDto setCourseClassrooms(Long id, IdsRequest request) { Course course = courseEntity(id); course.setClassrooms(new LinkedHashSet<>(request.ids().stream().map(this::classroomEntity).toList())); return course(courses.save(course)); }
    public EnrollmentDto enroll(Long courseId, Long studentId) {
        Enrollment existing = enrollments.findByCourseIdAndStudentId(courseId, studentId).orElse(null);
        if (existing != null) return enrollment(existing);
        return enrollment(enrollments.save(new Enrollment(courseEntity(courseId), studentEntity(studentId))));
    }
    public void unenroll(Long courseId, Long studentId) { enrollments.delete(enrollments.findByCourseIdAndStudentId(courseId, studentId).orElseThrow(() -> new NotFoundException("Enrollment not found."))); }
    @Transactional(readOnly = true) public List<EnrollmentDto> enrollments(Long courseId) { courseEntity(courseId); return enrollments.findByCourseId(courseId).stream().map(this::enrollment).toList(); }
    public CheckinSessionDto createSession(Long courseId, SessionRequest request) { return session(sessions.save(new CheckinSession(courseEntity(courseId), request.name(), request.startsAt()))); }
    public CheckinSessionDto endSession(Long id) { CheckinSession item = sessionEntity(id); item.end(null); return session(sessions.save(item)); }
    @Transactional(readOnly = true) public List<CheckinSessionDto> sessions(Long courseId) { courseEntity(courseId); return sessions.findByCourseIdOrderByStartsAtDesc(courseId).stream().map(this::session).toList(); }
    Classroom classroomEntity(Long id) { return classrooms.findById(id).orElseThrow(() -> new NotFoundException("Classroom not found.")); }
    Student studentEntity(Long id) { return students.findById(id).orElseThrow(() -> new NotFoundException("Student not found.")); }
    Course courseEntity(Long id) { return courses.findById(id).orElseThrow(() -> new NotFoundException("Course not found.")); }
    CheckinSession sessionEntity(Long id) { return sessions.findById(id).orElseThrow(() -> new NotFoundException("Check-in session not found.")); }
    Classroom classroomOrNull(Long id) { return id == null ? null : classroomEntity(id); }
    ClassroomDto classroom(Classroom x) { return new ClassroomDto(x.getId(), x.getCode(), x.getName(), x.getDescription()); }
    StudentDto student(Student x) { return new StudentDto(x.getId(), x.getStudentNumber(), x.getFullName(), x.getClassroom() == null ? null : x.getClassroom().getId(), x.getPhone()); }
    CourseDto course(Course x) { return new CourseDto(x.getId(), x.getCode(), x.getName(), x.getDescription(), x.getClassrooms().stream().map(Classroom::getId).sorted().toList()); }
    PhotoDto photo(StudentPhoto x) { return new PhotoDto(x.getId(), x.getStorageUri(), x.getContentHash(), x.isPrimary()); }
    EnrollmentDto enrollment(Enrollment x) { return new EnrollmentDto(x.getId(), x.getStudent().getId()); }
    CheckinSessionDto session(CheckinSession x) { return new CheckinSessionDto(x.getId(), x.getCourse().getId(), x.getName(), x.getStatus(), x.getStartsAt(), x.getEndsAt()); }
    private <T> T save(SupplierWithIntegrity<T> action) { try { return action.get(); } catch (DataIntegrityViolationException exception) { throw new ConflictException("A record with the same unique value already exists."); } }
    @FunctionalInterface private interface SupplierWithIntegrity<T> { T get(); }
}
