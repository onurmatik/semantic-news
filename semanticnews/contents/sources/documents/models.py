from openai import AsyncOpenAI, OpenAI
from django.db import models


class VectorStore(models.Model):
    name = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    vs_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Save the model
        super().save(*args, **kwargs)

        # If we haven’t uploaded yet, push to OpenAI and store the id.
        if not self.vs_id:
            client = OpenAI()

            vs_obj = client.vector_stores.create(
                name=self.name,
            )

            # Avoid a second `save()` call by using queryset.update()
            type(self).objects.filter(pk=self.pk).update(vs_id=vs_obj.id)


class VectorStoreFile(models.Model):
    name = models.CharField(max_length=500)
    document = models.FileField(upload_to='vector_files/')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    vector_store = models.ForeignKey(VectorStore, on_delete=models.SET_NULL, blank=True, null=True)
    file_id = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Save the model
        super().save(*args, **kwargs)

        # If we haven’t uploaded yet, push to OpenAI and store the id.
        if not self.file_id:
            client = OpenAI()

            with self.document.open('rb') as f:
                file_data = f.read()

            file_obj = client.vector_stores.files.upload_and_poll(
                vector_store_id=self.vector_store.vs_id,
                file=(self.document.name, file_data),
            )

            # Avoid a second `save()` call by using queryset.update()
            type(self).objects.filter(pk=self.pk).update(file_id=file_obj.id)
