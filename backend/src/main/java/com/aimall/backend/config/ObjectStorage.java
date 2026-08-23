package com.aimall.backend.config;

import io.minio.BucketExistsArgs;
import io.minio.GetObjectArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.io.InputStream;

/** 对象存储封装：启动时保证 bucket 存在；提供 put/get 两个最小操作 */
@Component
@RequiredArgsConstructor
public class ObjectStorage {

    private static final int STREAM_PART_SIZE = 10 * 1024 * 1024;

    private final MinioClient client;
    private final AppProperties props;

    @PostConstruct
    public void ensureBucket() {
        try {
            String bucket = props.getStorage().getBucket();
            if (!client.bucketExists(BucketExistsArgs.builder().bucket(bucket).build())) {
                client.makeBucket(MakeBucketArgs.builder().bucket(bucket).build());
            }
        } catch (Exception e) {
            throw new IllegalStateException("初始化对象存储 bucket 失败：" + e.getMessage(), e);
        }
    }

    public void put(String name, InputStream in, String contentType) throws Exception {
        client.putObject(PutObjectArgs.builder()
                .bucket(props.getStorage().getBucket())
                .object(name)
                .stream(in, -1, STREAM_PART_SIZE)
                .contentType(contentType)
                .build());
    }

    public byte[] get(String name) throws Exception {
        try (var s = client.getObject(GetObjectArgs.builder()
                .bucket(props.getStorage().getBucket()).object(name).build())) {
            return s.readAllBytes();
        }
    }
}