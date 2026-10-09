package com.aimall.backend.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 业务配置项（全部来自环境变量，禁止硬编码密钥）
 */
@Data
@ConfigurationProperties(prefix = "app")
public class AppProperties {

    private Jwt jwt = new Jwt();
    private Ai ai = new Ai();
    private Storage storage = new Storage();
    private Chat chat = new Chat();
    private Seed seed = new Seed();
    private Eval eval = new Eval();

    @Data
    public static class Jwt {
        private String secret;
        private long accessTtlMinutes = 120;
        private long refreshTtlDays = 7;
    }

    @Data
    public static class Ai {
        private String baseUrl;
        private String internalToken;
    }

    @Data
    public static class Storage {
        private String endpoint;
        private String accessKey;
        private String secretKey;
        private String bucket;
    }

    @Data
    public static class Chat {
        private int rateLimit = 20;
    }

    @Data
    public static class Seed {
        private String password;
        private KnowledgeBase knowledgeBase = new KnowledgeBase();
    }

    @Data
    public static class KnowledgeBase {
        private boolean enabled = true;
        private String manifest = "kbseed/generated/manifest.json";
        private int batchSize = 2;
        private int maxConcurrent = 4;
        private int stuckTimeoutSeconds = 900;
    }

    /** 评测体系配置：离线 eval 基准线文件路径等 */
    @Data
    public static class Eval {
        private String baselinePath;
    }
}

