package com.aimall.backend.chat;

import com.aimall.backend.entity.UserMemory;
import com.aimall.backend.mapper.UserMemoryMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

/**
 * 用户长期记忆管理服务：持久化跨会话的用户称谓、偏好与情景事实
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserMemoryService {

    private final UserMemoryMapper userMemoryMapper;

    /** 查询用户全部有效记忆 */
    public List<UserMemory> getMemoriesByUserId(Long userId) {
        if (userId == null) {
            return Collections.emptyList();
        }
        return userMemoryMapper.selectList(new LambdaQueryWrapper<UserMemory>()
                .eq(UserMemory::getUserId, userId)
                .orderByAsc(UserMemory::getCategory)
                .orderByAsc(UserMemory::getId));
    }

    /** 获取记忆 Map（memoryKey -> memoryValue）方便快速注入画像 */
    public Map<String, String> getMemoryMap(Long userId) {
        List<UserMemory> list = getMemoriesByUserId(userId);
        Map<String, String> map = new LinkedHashMap<>();
        for (UserMemory m : list) {
            if (m.getMemoryKey() != null && m.getMemoryValue() != null) {
                map.put(m.getMemoryKey(), m.getMemoryValue());
            }
        }
        return map;
    }

    /** 获取 DTO 列表格式，传给 AI 服务 */
    public List<Map<String, String>> getMemoriesDto(Long userId) {
        List<UserMemory> list = getMemoriesByUserId(userId);
        List<Map<String, String>> res = new ArrayList<>();
        for (UserMemory m : list) {
            Map<String, String> item = new HashMap<>();
            item.put("category", m.getCategory());
            item.put("key", m.getMemoryKey());
            item.put("value", m.getMemoryValue());
            res.add(item);
        }
        return res;
    }

    /** 写入或更新单条记忆 */
    @Transactional
    public void upsertMemory(Long userId, String category, String memoryKey, String memoryValue) {
        if (userId == null || memoryKey == null || memoryKey.isBlank() || memoryValue == null || memoryValue.isBlank()) {
            return;
        }
        String cat = (category == null || category.isBlank()) ? "FACT" : category.trim().toUpperCase();
        String key = memoryKey.trim();
        String val = memoryValue.trim();

        UserMemory existing = userMemoryMapper.selectOne(new LambdaQueryWrapper<UserMemory>()
                .eq(UserMemory::getUserId, userId)
                .eq(UserMemory::getCategory, cat)
                .eq(UserMemory::getMemoryKey, key));

        if (existing != null) {
            existing.setMemoryValue(val);
            existing.setUpdatedAt(LocalDateTime.now());
            userMemoryMapper.updateById(existing);
            log.info("updated user_memory: userId={} cat={} key={} val={}", userId, cat, key, val);
        } else {
            UserMemory record = new UserMemory();
            record.setUserId(userId);
            record.setCategory(cat);
            record.setMemoryKey(key);
            record.setMemoryValue(val);
            userMemoryMapper.insert(record);
            log.info("inserted user_memory: userId={} cat={} key={} val={}", userId, cat, key, val);
        }
    }

    /** 批量写入或更新多条记忆 */
    @Transactional
    public void batchUpsert(Long userId, List<Map<String, String>> items) {
        if (userId == null || items == null || items.isEmpty()) {
            return;
        }
        for (Map<String, String> item : items) {
            String cat = item.get("category");
            String key = item.get("key");
            String val = item.get("value");
            upsertMemory(userId, cat, key, val);
        }
    }

    /** 清空用户全部记忆 */
    @Transactional
    public void clearMemories(Long userId) {
        if (userId == null) {
            return;
        }
        userMemoryMapper.delete(new LambdaQueryWrapper<UserMemory>().eq(UserMemory::getUserId, userId));
        log.info("cleared user_memory for userId={}", userId);
    }
}
