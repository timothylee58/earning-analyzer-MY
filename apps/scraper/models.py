from django.db import models


class Company(models.Model):
    stock_code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.stock_code} {self.name}"


class Announcement(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="announcements"
    )
    ann_id = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=500)
    announced_at = models.DateTimeField()
    pdf_url = models.URLField(max_length=500, blank=True)
    pdf_path = models.CharField(max_length=500, blank=True)
    raw_text = models.TextField(blank=True)

    class Meta:
        ordering = ["-announced_at"]

    def __str__(self):
        return f"{self.company.stock_code}: {self.title[:60]}"


class AnalysisResult(models.Model):
    announcement = models.OneToOneField(
        Announcement, on_delete=models.CASCADE, related_name="analysis"
    )
    sentiment_label = models.CharField(max_length=10)
    sentiment_score = models.FloatField()
    n_sentences = models.IntegerField(default=0)
    n_xlmr_sentences = models.IntegerField(default=0)
    fls_count = models.IntegerField(default=0)
    fls_sentiment = models.FloatField(default=0.0)
    predicted_direction = models.CharField(max_length=5, blank=True)  # up/down
    created_at = models.DateTimeField(auto_now_add=True)
