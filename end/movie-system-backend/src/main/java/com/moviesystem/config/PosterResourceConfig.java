package com.moviesystem.config;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

@Configuration
public class PosterResourceConfig implements WebMvcConfigurer {

    @Value("${app.poster-dir:${user.home}/.movie-system/posters}")
    private String posterDir;

    @PostConstruct
    public void ensurePosterDir() throws IOException {
        Files.createDirectories(resolvePosterDir());
    }

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        String location = resolvePosterDir().toUri().toString();
        registry.addResourceHandler("/posters/**")
                .addResourceLocations(location);
    }

    private Path resolvePosterDir() {
        return Paths.get(posterDir).toAbsolutePath().normalize();
    }
}
