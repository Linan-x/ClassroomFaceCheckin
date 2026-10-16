package com.classroomfacecheckin.business.realtime;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.ChannelTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;

@Configuration
@ConditionalOnProperty(prefix = "realtime", name = "enabled", havingValue = "true")
class RealtimeRedisConfiguration {

    @Bean
    RedisMessageListenerContainer attendanceEventListenerContainer(
            RedisConnectionFactory connectionFactory, RedisAttendanceEventPublisher publisher) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(connectionFactory);
        container.addMessageListener(publisher, new ChannelTopic(RedisAttendanceEventPublisher.CHANNEL));
        return container;
    }
}
