package com.aimall.backend.chat;

import com.aimall.backend.entity.UserMemory;
import com.aimall.backend.mapper.UserMemoryMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class UserMemoryServiceTest {

    @Mock
    private UserMemoryMapper userMemoryMapper;

    @InjectMocks
    private UserMemoryService userMemoryService;

    @Test
    void getMemoryMapReturnsKeyValues() {
        UserMemory m1 = new UserMemory();
        m1.setId(1L);
        m1.setUserId(10L);
        m1.setCategory("IDENTITY");
        m1.setMemoryKey("user_name");
        m1.setMemoryValue("派蒙");

        UserMemory m2 = new UserMemory();
        m2.setId(2L);
        m2.setUserId(10L);
        m2.setCategory("IDENTITY");
        m2.setMemoryKey("assistant_name");
        m2.setMemoryValue("大肥鱼");

        when(userMemoryMapper.selectList(any())).thenReturn(List.of(m1, m2));

        Map<String, String> map = userMemoryService.getMemoryMap(10L);
        assertThat(map).containsEntry("user_name", "派蒙");
        assertThat(map).containsEntry("assistant_name", "大肥鱼");
    }

    @Test
    void upsertInsertsWhenNotPresent() {
        when(userMemoryMapper.selectOne(any())).thenReturn(null);

        userMemoryService.upsertMemory(10L, "IDENTITY", "user_name", "派蒙");

        verify(userMemoryMapper).insert(any(UserMemory.class));
    }

    @Test
    void upsertUpdatesWhenPresent() {
        UserMemory existing = new UserMemory();
        existing.setId(5L);
        existing.setUserId(10L);
        existing.setCategory("IDENTITY");
        existing.setMemoryKey("user_name");
        existing.setMemoryValue("旧名字");

        when(userMemoryMapper.selectOne(any())).thenReturn(existing);

        userMemoryService.upsertMemory(10L, "IDENTITY", "user_name", "派蒙");

        verify(userMemoryMapper).updateById(any(UserMemory.class));
    }
}
