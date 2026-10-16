package com.classroomfacecheckin.business.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "enrollments", uniqueConstraints = @UniqueConstraint(name = "uk_enrollments_course_student", columnNames = {"course_id", "student_id"}))
public class Enrollment {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "course_id", nullable = false) private Course course;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "student_id", nullable = false) private Student student;
    @Column(name = "enrolled_at", nullable = false) private Instant enrolledAt = Instant.now();
    protected Enrollment() {}
    public Enrollment(Course course, Student student) { this.course = course; this.student = student; }
    public Long getId() { return id; } public Course getCourse() { return course; } public Student getStudent() { return student; }
}
