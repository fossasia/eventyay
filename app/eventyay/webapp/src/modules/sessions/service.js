export default {
    async fetchSchedule(url) {
        const response = await fetch(url)
        if (!response.ok) throw new Error(`Failed to fetch schedule: ${response.statusText}`)
        return response.json()
    }
}
