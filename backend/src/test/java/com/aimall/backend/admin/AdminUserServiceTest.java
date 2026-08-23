package com.aimall.backend.admin;

import com.aimall.backend.common.BizException;
import com.aimall.backend.common.PageResult;
import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import org.apache.ibatis.builder.MapperBuilderAssistant;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.security.crypto.password.PasswordEncoder;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.*;

@SuppressWarnings("unchecked")
class AdminUserServiceTest {

    @BeforeAll
    static void initUserTableInfo() {
        TableInfoHelper.initTableInfo(new MapperBuilderAssistant(new MybatisConfiguration(), ""), User.class);
    }

    private final UserMapper userMapper = mock(UserMapper.class);
    private final PasswordEncoder passwordEncoder = mock(PasswordEncoder.class);
    private final AdminUserService service = new AdminUserService(userMapper, passwordEncoder);

    @Test
    void createsActiveAgentWithServerFixedRole() {
        when(userMapper.selectCount(any())).thenReturn(0L);
        when(passwordEncoder.encode("123456")).thenReturn("hashed-password");
        when(userMapper.insert(any(User.class))).thenAnswer(i -> {
            i.<User>getArgument(0).setId(12L);
            return 1;
        });

        Long id = service.createAgent(agentRequest(" agent02 "));

        assertThat(id).isEqualTo(12L);
        verify(userMapper).insert(argThat((User u) -> "agent02".equals(u.getUsername())
                && "hashed-password".equals(u.getPassword())
                && "AGENT".equals(u.getRole()) && "ACTIVE".equals(u.getStatus())));
    }

    @Test
    void preservesAgentPasswordWhitespaceWhenEncoding() {
        when(userMapper.selectCount(any())).thenReturn(0L);
        when(userMapper.insert(any(User.class))).thenAnswer(i -> {
            i.<User>getArgument(0).setId(13L);
            return 1;
        });
        AdminUserService.CreateAgentRequest request = agentRequest("agent03");
        request.setPassword(" 123456 ");

        service.createAgent(request);

        verify(passwordEncoder).encode(" 123456 ");
    }

    @Test
    void convertsAgentInsertDuplicateKeyToUsernameConflict() {
        when(userMapper.selectCount(any())).thenReturn(0L);
        when(userMapper.insert(any(User.class))).thenThrow(new DuplicateKeyException("uk_user_username"));

        assertThatThrownBy(() -> service.createAgent(agentRequest("agent02")))
                .isInstanceOfSatisfying(BizException.class, error -> {
                    assertThat(error.getCode()).isEqualTo(2005);
                    assertThat(error.getMessage()).isEqualTo("用户名已存在");
                });
    }

    @Test
    void rejectsDuplicateAgentUsername() {
        when(userMapper.selectCount(any())).thenReturn(1L);

        assertThatThrownBy(() -> service.createAgent(agentRequest("agent02")))
                .isInstanceOf(BizException.class).hasMessageContaining("用户名已存在");
        verify(userMapper, never()).insert(any(User.class));
    }

    @Test
    void listsOnlyNonAdminUsersAndAllowsCustomerMerchantAndAgentFilters() {
        Page<User> users = new Page<>(1, 20);
        users.setRecords(java.util.List.of(user(22L, "CUSTOMER")));
        users.setTotal(1);
        when(userMapper.selectPage(any(), any())).thenReturn(users);

        PageResult<java.util.Map<String, Object>> result = service.list("CUSTOMER", "buyer", 1, 20);

        assertThat(result.getRecords()).singleElement().satisfies(vo -> {
            assertThat(vo).containsEntry("userId", 22L).containsEntry("role", "CUSTOMER");
        });
        ArgumentCaptor<LambdaQueryWrapper<User>> wrapper = ArgumentCaptor.forClass(LambdaQueryWrapper.class);
        verify(userMapper).selectPage(any(), wrapper.capture());
        assertThat(wrapper.getValue().getSqlSegment()).contains("role <>").contains("role =").contains("username");
    }

    @Test
    void rejectsAdminAndUnknownRoleFilters() {
        assertThatThrownBy(() -> service.list("ADMIN", null, 1, 20)).isInstanceOf(BizException.class);
        assertThatThrownBy(() -> service.list("UNKNOWN", null, 1, 20)).isInstanceOf(BizException.class);
        verifyNoInteractions(userMapper);
    }

    @Test
    void updatesOnlyStatusForNonAdminNonSelfTarget() {
        when(userMapper.selectById(22L)).thenReturn(user(22L, "AGENT"));

        service.updateStatus(1L, 22L, "DISABLED");

        verify(userMapper).updateById(argThat((User u) -> u.getId().equals(22L)
                && "DISABLED".equals(u.getStatus()) && u.getRole() == null));
    }

    @Test
    void rejectsInvalidStatusAdminAndSelfTargets() {
        assertThatThrownBy(() -> service.updateStatus(1L, 22L, "PENDING")).isInstanceOf(BizException.class);

        when(userMapper.selectById(1L)).thenReturn(user(1L, "AGENT"));
        assertThatThrownBy(() -> service.updateStatus(1L, 1L, "DISABLED")).isInstanceOf(BizException.class);

        when(userMapper.selectById(2L)).thenReturn(user(2L, "ADMIN"));
        assertThatThrownBy(() -> service.updateStatus(1L, 2L, "DISABLED")).isInstanceOf(BizException.class);
        verify(userMapper, never()).updateById(any(User.class));
    }

    private static AdminUserService.CreateAgentRequest agentRequest(String username) {
        AdminUserService.CreateAgentRequest request = new AdminUserService.CreateAgentRequest();
        request.setUsername(username);
        request.setPassword("123456");
        request.setNickname("客服");
        request.setPhone("13800000000");
        return request;
    }

    private static User user(Long id, String role) {
        User user = new User();
        user.setId(id);
        user.setUsername("user" + id);
        user.setNickname("用户" + id);
        user.setPhone("13800000000");
        user.setRole(role);
        user.setStatus("ACTIVE");
        return user;
    }
}
