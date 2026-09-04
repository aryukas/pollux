import { useRef, useState } from "react"
import { Button } from "@/components/ui/button"

const API_URL = "http://127.0.0.1:8000"

const ALLOWED_TYPES = [
  "image/jpeg",
  "image/png",
  "application/pdf",
]

function App() {
  const fileInputRef = useRef(null)

  const [file, setFile] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [status, setStatus] = useState("")
  const [error, setError] = useState("")

  const handleFile = (selectedFile) => {
    if (!selectedFile) return

    setStatus("")
    setError("")

    if (!ALLOWED_TYPES.includes(selectedFile.type)) {
      setFile(null)
      setError("Please select a JPG, JPEG, PNG, or PDF file.")
      return
    }

    setFile(selectedFile)
  }

  const handleFileChange = (event) => {
    handleFile(event.target.files?.[0])
  }

  const handleDrop = (event) => {
    event.preventDefault()
    setIsDragging(false)

    handleFile(event.dataTransfer.files?.[0])
  }

  const handleUpload = async () => {
    if (!file || isUploading) return

    setIsUploading(true)
    setStatus("Uploading...")
    setError("")

    const formData = new FormData()
    formData.append("file", file)

    try {
      const response = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Upload failed.")
      }

      setStatus(`File accepted: ${data.filename}`)
    } catch (err) {
      setStatus("")
      setError(
        err.message || "Unable to connect to the Pollux backend."
      )
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <main className="min-h-screen bg-background px-6 py-12">
      <div className="mx-auto flex min-h-[80vh] max-w-3xl flex-col items-center justify-center">

        {/* Header */}
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-semibold tracking-tight">
            Pollux
          </h1>

          <p className="mt-3 text-lg text-muted-foreground">
            Cash Flow Statement Extractor
          </p>

          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Upload a financial document and convert its Cash Flow Statement
            into structured, editable data.
          </p>
        </div>

        {/* Upload Area */}
        <div
          onDragOver={(event) => {
            event.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`w-full rounded-xl border-2 border-dashed p-12 text-center transition ${
            isDragging
              ? "border-primary bg-muted/50"
              : "border-muted-foreground/25"
          }`}
        >
          <div className="mx-auto max-w-md">

            <h2 className="text-lg font-medium">
              {file ? file.name : "Drop your document here"}
            </h2>

            <p className="mt-2 text-sm text-muted-foreground">
              {file
                ? `${(file.size / 1024 / 1024).toFixed(2)} MB`
                : "or choose a file from your device"}
            </p>

            {/* Hidden File Input */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".jpg,.jpeg,.png,.pdf"
              onChange={handleFileChange}
              className="hidden"
            />

            {/* Choose File */}
            <Button
              className="mt-6"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              Choose File
            </Button>

            <p className="mt-4 text-xs text-muted-foreground">
              JPG, JPEG, PNG or PDF
            </p>

          </div>
        </div>

        {/* Extract Button */}
        {file && (
          <Button
            className="mt-6"
            onClick={handleUpload}
            disabled={isUploading}
          >
            {isUploading
              ? "Uploading..."
              : "Extract Cash Flow Statement"}
          </Button>
        )}

        {/* Success Status */}
        {status && (
          <p className="mt-4 text-sm text-green-600">
            {status}
          </p>
        )}

        {/* Error Status */}
        {error && (
          <p className="mt-4 text-sm text-destructive">
            {error}
          </p>
        )}

      </div>
    </main>
  )
}

export default App