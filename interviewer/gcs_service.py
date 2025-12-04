"""
Google Cloud Storage Service dla agenta.
Umożliwia przesyłanie plików i danych do GCS bucket.
"""

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from typing import Optional, Union, BinaryIO
import os
from datetime import datetime
import json


class GCSService:
    """Serwis do zarządzania operacjami na Google Cloud Storage."""
    
    def __init__(self, bucket_name: str, project_id: Optional[str] = None):
        """
        Inicjalizacja serwisu GCS.
        
        Args:
            bucket_name: Nazwa bucket GCS
            project_id: ID projektu GCP (opcjonalne, domyślnie z ADC)
        """
        self.bucket_name = bucket_name
        self.project_id = project_id
        self.client = storage.Client(project=project_id)
        self.bucket = self.client.bucket(bucket_name)
    
    def upload_file(
        self,
        source_file_path: str,
        destination_blob_name: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> str:
        """
        Przesyła plik lokalny do GCS.
        
        Args:
            source_file_path: Ścieżka do pliku lokalnego
            destination_blob_name: Nazwa pliku w GCS (opcjonalnie, domyślnie nazwa pliku lokalnego)
            content_type: Typ contentu (opcjonalnie)
            
        Returns:
            Publiczny URL do pliku w GCS
            
        Raises:
            FileNotFoundError: Gdy plik nie istnieje
            GoogleCloudError: Przy błędzie przesyłania
        """
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"Plik {source_file_path} nie istnieje")
        
        if destination_blob_name is None:
            destination_blob_name = os.path.basename(source_file_path)
        
        blob = self.bucket.blob(destination_blob_name)
        
        if content_type:
            blob.content_type = content_type
        
        blob.upload_from_filename(source_file_path)
        
        return f"gs://{self.bucket_name}/{destination_blob_name}"
    
    def upload_string(
        self,
        data: str,
        destination_blob_name: str,
        content_type: str = "text/plain"
    ) -> str:
        """
        Przesyła dane tekstowe do GCS.
        
        Args:
            data: Dane tekstowe do przesłania
            destination_blob_name: Nazwa pliku w GCS
            content_type: Typ contentu
            
        Returns:
            Publiczny URL do pliku w GCS
        """
        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_string(data, content_type=content_type)
        
        return f"gs://{self.bucket_name}/{destination_blob_name}"
    
    def upload_json(
        self,
        data: dict,
        destination_blob_name: str
    ) -> str:
        """
        Przesyła dane JSON do GCS.
        
        Args:
            data: Słownik do zapisania jako JSON
            destination_blob_name: Nazwa pliku w GCS
            
        Returns:
            Publiczny URL do pliku w GCS
        """
        json_string = json.dumps(data, indent=2, ensure_ascii=False)
        return self.upload_string(
            json_string,
            destination_blob_name,
            content_type="application/json"
        )
    
    def upload_from_stream(
        self,
        file_obj: BinaryIO,
        destination_blob_name: str,
        content_type: Optional[str] = None
    ) -> str:
        """
        Przesyła dane ze strumienia (file-like object) do GCS.
        
        Args:
            file_obj: Obiekt pliku lub strumień danych
            destination_blob_name: Nazwa pliku w GCS
            content_type: Typ contentu
            
        Returns:
            Publiczny URL do pliku w GCS
        """
        blob = self.bucket.blob(destination_blob_name)
        
        if content_type:
            blob.content_type = content_type
        
        blob.upload_from_file(file_obj)
        
        return f"gs://{self.bucket_name}/{destination_blob_name}"
    
    def list_files(self, prefix: Optional[str] = None) -> list[str]:
        """
        Listuje pliki w bucket.
        
        Args:
            prefix: Opcjonalny prefix do filtrowania
            
        Returns:
            Lista nazw plików
        """
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        return [blob.name for blob in blobs]
    
    def download_file(
        self,
        source_blob_name: str,
        destination_file_path: str
    ) -> str:
        """
        Pobiera plik z GCS do lokalnego systemu.
        
        Args:
            source_blob_name: Nazwa pliku w GCS
            destination_file_path: Ścieżka docelowa w lokalnym systemie
            
        Returns:
            Ścieżka do pobranego pliku
        """
        blob = self.bucket.blob(source_blob_name)
        blob.download_to_filename(destination_file_path)
        
        return destination_file_path
    
    def download_as_string(self, source_blob_name: str) -> str:
        """
        Pobiera plik z GCS jako string.
        
        Args:
            source_blob_name: Nazwa pliku w GCS
            
        Returns:
            Zawartość pliku jako string
        """
        blob = self.bucket.blob(source_blob_name)
        return blob.download_as_text()
    
    def delete_file(self, blob_name: str) -> bool:
        """
        Usuwa plik z GCS.
        
        Args:
            blob_name: Nazwa pliku w GCS
            
        Returns:
            True jeśli usunięto pomyślnie
        """
        blob = self.bucket.blob(blob_name)
        blob.delete()
        return True
    
    def file_exists(self, blob_name: str) -> bool:
        """
        Sprawdza czy plik istnieje w GCS.
        
        Args:
            blob_name: Nazwa pliku w GCS
            
        Returns:
            True jeśli plik istnieje
        """
        blob = self.bucket.blob(blob_name)
        return blob.exists()
    
    def get_file_url(self, blob_name: str, signed: bool = False, expiration: int = 3600) -> str:
        """
        Zwraca URL do pliku w GCS.
        
        Args:
            blob_name: Nazwa pliku w GCS
            signed: Czy generować podpisany URL (domyślnie False)
            expiration: Czas wygaśnięcia podpisanego URL w sekundach (domyślnie 1h)
            
        Returns:
            URL do pliku
        """
        blob = self.bucket.blob(blob_name)
        
        if signed:
            return blob.generate_signed_url(expiration=expiration)
        else:
            return f"gs://{self.bucket_name}/{blob_name}"
    
    def upload_with_metadata(
        self,
        source_file_path: str,
        destination_blob_name: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """
        Przesyła plik z dodatkowymi metadanymi.
        
        Args:
            source_file_path: Ścieżka do pliku lokalnego
            destination_blob_name: Nazwa pliku w GCS
            metadata: Słownik z metadanymi
            
        Returns:
            Publiczny URL do pliku w GCS
        """
        if not os.path.exists(source_file_path):
            raise FileNotFoundError(f"Plik {source_file_path} nie istnieje")
        
        if destination_blob_name is None:
            destination_blob_name = os.path.basename(source_file_path)
        
        blob = self.bucket.blob(destination_blob_name)
        
        if metadata:
            blob.metadata = metadata
        
        blob.upload_from_filename(source_file_path)
        
        return f"gs://{self.bucket_name}/{destination_blob_name}"


# Przykładowe użycie z funkcjami pomocniczymi dla agenta
def create_timestamped_filename(base_name: str, extension: str = "json") -> str:
    """
    Tworzy nazwę pliku z znacznikiem czasu.
    
    Args:
        base_name: Podstawowa nazwa pliku
        extension: Rozszerzenie pliku
        
    Returns:
        Nazwa pliku z timestampem
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.{extension}"


def upload_agent_output(
    gcs_service: GCSService,
    data: dict,
    output_type: str = "response"
) -> str:
    """
    Funkcja pomocnicza do przesyłania wyników działania agenta.
    
    Args:
        gcs_service: Instancja GCSService
        data: Dane do przesłania
        output_type: Typ outputu (używany w nazwie pliku)
        
    Returns:
        URL do przesłanego pliku
    """
    filename = create_timestamped_filename(f"agent_{output_type}")
    return gcs_service.upload_json(data, filename)
