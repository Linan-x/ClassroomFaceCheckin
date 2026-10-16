package com.classroomfacecheckin.business.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "student_photos")
public class StudentPhoto {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "student_id", nullable = false) private Student student;
    @Column(name = "storage_uri", nullable = false, length = 512) private String storageUri;
    @Column(name = "content_hash", length = 128) private String contentHash;
    @Column(name = "is_primary", nullable = false) private boolean primary;
    @Column(name = "created_at", nullable = false) private Instant createdAt = Instant.now();
    protected StudentPhoto() {}
    public StudentPhoto(Student student, String storageUri, String contentHash, boolean primary) { this.student = student; this.storageUri = storageUri; this.contentHash = contentHash; this.primary = primary; }
    public Long getId() { return id; } public Student getStudent() { return student; } public String getStorageUri() { return storageUri; }
    public String getContentHash() { return contentHash; } public boolean isPrimary() { return primary; }
}
