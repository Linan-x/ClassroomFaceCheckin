package com.classroomfacecheckin.business.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "classrooms")
public class Classroom {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @Column(nullable = false, unique = true, length = 64) private String code;
    @Column(nullable = false, length = 128) private String name;
    @Column(length = 500) private String description;
    @Column(name = "legacy_key", unique = true, length = 255) private String legacyKey;
    @Column(name = "created_at", nullable = false) private Instant createdAt = Instant.now();
    @Column(name = "updated_at", nullable = false) private Instant updatedAt = Instant.now();
    protected Classroom() {}
    public Classroom(String code, String name, String description) { this.code = code; this.name = name; this.description = description; }
    @PreUpdate void touch() { updatedAt = Instant.now(); }
    public Long getId() { return id; } public String getCode() { return code; } public String getName() { return name; }
    public String getDescription() { return description; } public String getLegacyKey() { return legacyKey; }
    public void update(String code, String name, String description) { this.code = code; this.name = name; this.description = description; }
    public void setLegacyKey(String legacyKey) { this.legacyKey = legacyKey; }
}
