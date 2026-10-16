package com.classroomfacecheckin.business.domain;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.Set;

@Entity
@Table(name = "courses")
public class Course {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(nullable = false, unique = true, length = 64) private String code;
    @Column(nullable = false, length = 128) private String name;
    @Column(length = 500) private String description;
    @Column(name = "legacy_key", unique = true, length = 255) private String legacyKey;
    @ManyToMany @JoinTable(name = "course_classrooms", joinColumns = @JoinColumn(name = "course_id"), inverseJoinColumns = @JoinColumn(name = "classroom_id"))
    private Set<Classroom> classrooms = new LinkedHashSet<>();
    @Column(name = "created_at", nullable = false) private Instant createdAt = Instant.now();
    @Column(name = "updated_at", nullable = false) private Instant updatedAt = Instant.now();
    protected Course() {}
    public Course(String code, String name, String description) { this.code = code; this.name = name; this.description = description; }
    @PreUpdate void touch() { updatedAt = Instant.now(); }
    public Long getId() { return id; } public String getCode() { return code; } public String getName() { return name; } public String getDescription() { return description; }
    public String getLegacyKey() { return legacyKey; } public Set<Classroom> getClassrooms() { return classrooms; }
    public void update(String code, String name, String description) { this.code = code; this.name = name; this.description = description; }
    public void setClassrooms(Set<Classroom> classrooms) { this.classrooms = classrooms; } public void setLegacyKey(String legacyKey) { this.legacyKey = legacyKey; }
}
