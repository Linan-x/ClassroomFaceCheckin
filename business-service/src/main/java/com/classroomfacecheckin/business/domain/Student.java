package com.classroomfacecheckin.business.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "students")
public class Student {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(name = "student_number", nullable = false, unique = true, length = 64) private String studentNumber;
    @Column(name = "full_name", nullable = false, length = 128) private String fullName;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "classroom_id") private Classroom classroom;
    @Column(length = 64) private String phone;
    @Column(name = "legacy_key", unique = true, length = 255) private String legacyKey;
    @Column(name = "created_at", nullable = false) private Instant createdAt = Instant.now();
    @Column(name = "updated_at", nullable = false) private Instant updatedAt = Instant.now();
    protected Student() {}
    public Student(String number, String name, Classroom classroom, String phone) { this.studentNumber = number; this.fullName = name; this.classroom = classroom; this.phone = phone; }
    @PreUpdate void touch() { updatedAt = Instant.now(); }
    public Long getId() { return id; } public String getStudentNumber() { return studentNumber; } public String getFullName() { return fullName; }
    public Classroom getClassroom() { return classroom; } public String getPhone() { return phone; } public String getLegacyKey() { return legacyKey; }
    public void update(String number, String name, Classroom classroom, String phone) { studentNumber = number; fullName = name; this.classroom = classroom; this.phone = phone; }
    public void setLegacyKey(String legacyKey) { this.legacyKey = legacyKey; }
}
