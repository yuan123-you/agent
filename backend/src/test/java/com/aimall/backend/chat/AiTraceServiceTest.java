package com.aimall.backend.chat;

import com.aimall.backend.entity.AiTrace;
import com.aimall.backend.mapper.AiTraceMapper;
import org.junit.jupiter.api.Test;
import java.time.LocalDateTime;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.*;

class AiTraceServiceTest {
    AiTraceMapper mapper = mock(AiTraceMapper.class);
    AiTraceService service = new AiTraceService(mapper);
    AiTrace existing() {
        var row=new AiTrace(); row.setId(1L); row.setTraceId("server-run"); row.setStatus("RUNNING");
        row.setConversationId(7L); row.setUserId(1L); row.setCreatedAt(LocalDateTime.now());
        when(mapper.selectOne(any())).thenReturn(row); return row;
    }
    @Test void identityIsServerOwnedAndSecretsAreRedactedAtIngress() {
        var row=existing();
        service.record("server-run", "{\"traceId\":\"server-run\",\"userId\":999,\"stages\":[{\"name\":\"model\",\"kind\":\"model\",\"input\":{\"api_key\":\"very-secret\"},\"output\":{\"reasoning_content\":\"private thoughts\"}}]}");
        assertThat(row.getUserId()).isEqualTo(1L);
        var captured=org.mockito.ArgumentCaptor.forClass(AiTrace.class); verify(mapper).updateById(captured.capture());
        var update=captured.getValue();
        assertThat(update.getDetailJson()).doesNotContain("very-secret", "private thoughts");
        assertThat(update.getModelCalls()).isEqualTo(1);
        assertThat(update.getTotalTokens()).isNull();
        assertThat(update.getStatus()).isNull();
        assertThat(update.getUserId()).isNull();
    }
    @Test void rejectsSnapshotsBoundToAnotherRequest() {
        existing(); service.record("server-run", "{\"traceId\":\"other\",\"stages\":[]}");
        verify(mapper, never()).updateById(any(AiTrace.class));
    }
    @Test void traceStorageFailureMustNotBreakChat() {
        doThrow(new IllegalStateException("offline")).when(mapper).insert(any(AiTrace.class));
        assertThatCode(() -> service.begin(1L,7L,"hello")).doesNotThrowAnyException();
    }
    @Test void terminalStatusAndMessageAreRecordedForOfflineAi() {
        var row=existing(); service.finish("server-run",42L,"FAILED");
        var captured=org.mockito.ArgumentCaptor.forClass(AiTrace.class); verify(mapper).updateById(captured.capture());
        assertThat(captured.getValue().getStatus()).isEqualTo("FAILED");
        assertThat(captured.getValue().getMessageId()).isEqualTo(42L);
        assertThat(captured.getValue().getFinishedAt()).isNotNull();
        assertThat(captured.getValue().getDetailJson()).isNull();
    }
    @Test void paginationIsBoundedAndListNeverSelectsLargePayloads() {
        var config=new com.baomidou.mybatisplus.core.MybatisConfiguration();
        com.baomidou.mybatisplus.core.metadata.TableInfoHelper.initTableInfo(
            new org.apache.ibatis.builder.MapperBuilderAssistant(config,"trace-test"),AiTrace.class);
        when(mapper.selectPage(any(),any())).thenAnswer(call->call.getArgument(0));
        var result=service.list(null,7L,"手机",0,1000);
        assertThat(result.getPage()).isEqualTo(1);assertThat(result.getSize()).isEqualTo(100);
        var query=org.mockito.ArgumentCaptor.forClass(com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper.class);
        verify(mapper).selectPage(any(),query.capture());
        assertThat(query.getValue().getSqlSelect()).doesNotContain("detail_json");
    }
    @Test void benchmarkReportIsLoadedFromClasspathOrFallback() {
        var report = service.getLatestBenchmark();
        assertThat(report).isNotEmpty();
        assertThat(report.get("overall_score")).isNotNull();
    }

}
