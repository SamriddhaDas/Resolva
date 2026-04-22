// Complaint priority classifier.
// Reads complaint text from STDIN, prints one of:
//   low | medium | high | critical
//
// Build:
//   g++ -O2 -std=c++17 classifier.cpp -o classifier
//
// Strategy: weighted keyword scoring + length & punctuation signals.

#include <algorithm>
#include <cctype>
#include <iostream>
#include <sstream>
#include <string>
#include <unordered_map>

static std::string to_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    return s;
}

int main() {
    std::ostringstream ss;
    ss << std::cin.rdbuf();
    std::string text = to_lower(ss.str());

    // Keyword weights
    std::unordered_map<std::string, int> weights = {
        {"emergency", 5}, {"urgent", 4}, {"immediately", 4}, {"asap", 3},
        {"danger", 5}, {"unsafe", 4}, {"injury", 5}, {"injured", 5},
        {"fire", 5}, {"flood", 5}, {"leak", 3}, {"electric", 3},
        {"shock", 4}, {"hazard", 4}, {"broken", 2}, {"damaged", 2},
        {"crash", 4}, {"down", 2}, {"outage", 3}, {"not working", 2},
        {"stolen", 4}, {"theft", 4}, {"harass", 5}, {"threat", 5},
        {"medical", 4}, {"blood", 4}, {"critical", 5},
        {"slow", 1}, {"minor", -1}, {"small", -1}, {"suggestion", -2},
        {"thanks", -2}, {"please", 0}
    };

    int score = 0;
    for (const auto& kv : weights) {
        size_t pos = 0;
        while ((pos = text.find(kv.first, pos)) != std::string::npos) {
            score += kv.second;
            pos += kv.first.size();
        }
    }

    // Punctuation / shouting signals (count from raw text via length proxy)
    int exclam = std::count(text.begin(), text.end(), '!');
    score += std::min(exclam, 5);

    // Long detailed reports get a small bump
    if (text.size() > 400) score += 1;
    if (text.size() > 1200) score += 2;

    std::string priority;
    if (score >= 9)      priority = "critical";
    else if (score >= 5) priority = "high";
    else if (score >= 2) priority = "medium";
    else                 priority = "low";

    std::cout << priority << std::endl;
    return 0;
}
