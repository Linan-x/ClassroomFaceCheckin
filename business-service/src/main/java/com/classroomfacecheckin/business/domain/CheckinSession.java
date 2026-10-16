package com.classroomfacecheckin.business.domain;

import jakarta.persistence.*;
import java.time.Instant;

@Entity
@Table(name = "checkin_sessions")
public class CheckinSession {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY) @JoinColumn(name = "course_id", nullable = false) private Course course;
    @Column(nullable = false, length = 128) private String name;
    @Column(nullable = false, length = 32) private String status;
    @Column(name = "starts_at") private Instant startsAt;
    @Column(name = "ends_at") private Instant endsAt;
    @Column(name = "legacy_key", unique = true, length = 255) private String legacyKey;
    @Column(name = "created_at", nullable = false) private Instant createdAt = Instant.now();
    @Column(name = "updated_at", nullable = false) private Instant updatedAt = Instant.now();
    protected CheckinSession() {}
    public CheckinSession(Course course, String name, Instant startsAt) { this.course = course; this.name = name; this.startsAt = startsAt == null ? Instant.now() : startsAt; this.status = "ACTIVE"; }
    public static CheckinSession imported(Course course, String name, Instant startsAt, boolean active) {
        CheckinSession session = new CheckinSession(course, name, startsAt);
        if (!active) { session.status = "ENDED"; session.endsAt = session.startsAt; }
        return session;
    }
    @PreUpdate void touch() { updatedAt = Instant.now(); }
    public Long getId() { return id; } public Course getCourse() { return course; } public String getName() { return name; } public String getStatus() { return status; }
    public Instant getStartsAt() { return startsAt; } public Instant getEndsAt() { return endsAt; } public String getLegacyKey() { return legacyKey; }
    public void end(Instant endedAt) { if (!"ACTIVE".equals(status)) throw new IllegalStateException("Check-in session is already ended."); status = "ENDED"; endsAt = endedAt == null ? Instant.now() : endedAt; }
    public void setLegacyKey(String legacyKey) { this.legacyKey = legacyKey; }
}
