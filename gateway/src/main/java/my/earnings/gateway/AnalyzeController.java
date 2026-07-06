package my.earnings.gateway;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestClient;

/**
 * Thin gateway in front of the Django NLP service. Owns cross-cutting
 * concerns (auth, rate limiting, request logging) so the Python service
 * stays a pure model-serving layer.
 */
@RestController
public class AnalyzeController {

    private final RestClient client;

    public AnalyzeController(@Value("${nlp.base-url}") String nlpBaseUrl) {
        this.client = RestClient.builder().baseUrl(nlpBaseUrl).build();
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        String body = client.get().uri("/api/health").retrieve().body(String.class);
        return ResponseEntity.ok(body);
    }

    @PostMapping(value = "/analyze", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<String> analyze(@RequestBody String payload) {
        String body = client.post()
                .uri("/api/analyze")
                .contentType(MediaType.APPLICATION_JSON)
                .body(payload)
                .retrieve()
                .body(String.class);
        return ResponseEntity.ok(body);
    }
}
