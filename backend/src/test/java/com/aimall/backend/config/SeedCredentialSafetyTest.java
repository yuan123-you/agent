package com.aimall.backend.config;

import com.aimall.backend.entity.User;
import com.aimall.backend.mapper.UserMapper;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.password.PasswordEncoder;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class SeedCredentialSafetyTest {
  @Test void seedConfigurationHasNoPublishedDefaultPassword() {
    assertTrue(new AppProperties().getSeed().getPassword() == null
        || new AppProperties().getSeed().getPassword().isBlank());
  }
  @Test void unconfiguredSeedPasswordFailsBeforeAnyWrite() {
    var mapper = mock(UserMapper.class);
    var encoder = mock(PasswordEncoder.class);
    when(mapper.selectList(any())).thenReturn(List.of(new User()));
    var props = new AppProperties();
    props.getSeed().setPassword("");
    var runner = new SeedDataInitializer().seedPasswordResetter(mapper, encoder, props);
    assertThrows(IllegalStateException.class, () -> runner.run(null));
    verifyNoInteractions(encoder);
    verify(mapper, never()).updateById(any(User.class));
  }
  @Test void existingDatabaseNeedsNoSeedPassword() {
    var mapper = mock(UserMapper.class);
    when(mapper.selectList(any())).thenReturn(List.of());
    var props = new AppProperties(); props.getSeed().setPassword("");
    var runner = new SeedDataInitializer().seedPasswordResetter(mapper, mock(PasswordEncoder.class), props);
    assertDoesNotThrow(() -> runner.run(null));
  }
}
