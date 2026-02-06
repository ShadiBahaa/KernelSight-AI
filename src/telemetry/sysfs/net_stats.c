// SPDX-License-Identifier: MIT
// Copyright (c) 2025 KernelSight AI
//
// Network statistics scraper implementation

#include "net_stats.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROC_NET_DEV "/proc/net/dev"
#define PROC_NET_TCP "/proc/net/tcp"
#define PROC_NET_TCP6 "/proc/net/tcp6"
#define PROC_NET_SNMP "/proc/net/snmp"

int read_net_dev(struct interface_stats **interfaces, int *count)
{
    FILE *fp;
    char line[512];
    struct interface_stats *if_list = NULL;
    int if_count = 0;
    int capacity = 16;

    if (!interfaces || !count) {
        return -1;
    }

    fp = fopen(PROC_NET_DEV, "r");
    if (!fp) {
        fprintf(stderr, "ERROR: failed to open %s\n", PROC_NET_DEV);
        return -1;
    }

    // Allocate initial array
    if_list = malloc(capacity * sizeof(struct interface_stats));
    if (!if_list) {
        fclose(fp);
        return -1;
    }

    // Skip first two header lines
    fgets(line, sizeof(line), fp);
    fgets(line, sizeof(line), fp);

    // Parse interface lines
    while (fgets(line, sizeof(line), fp)) {
        struct interface_stats iface;
        char *colon = strchr(line, ':');
        if (!colon) {
            continue;
        }

        // Parse interface name (before colon)
        *colon = '\0';
        char *name_start = line;
        while (*name_start == ' ' || *name_start == '\t') {
            name_start++;
        }
        strncpy(iface.name, name_start, sizeof(iface.name) - 1);
        iface.name[sizeof(iface.name) - 1] = '\0';

        // Parse statistics (after colon)
        // Format: RX (bytes packets errs drop fifo frame compressed multicast)
        //         TX (bytes packets errs drop fifo colls carrier compressed)
        int ret = sscanf(colon + 1,
                         "%lu %lu %lu %lu %*u %*u %*u %*u "
                         "%lu %lu %lu %lu",
                         &iface.rx_bytes, &iface.rx_packets, &iface.rx_errors, &iface.rx_drops,
                         &iface.tx_bytes, &iface.tx_packets, &iface.tx_errors, &iface.tx_drops);

        if (ret != 8) {
            continue;
        }

        // Expand array if needed
        if (if_count >= capacity) {
            capacity *= 2;
            struct interface_stats *new_list =
                realloc(if_list, capacity * sizeof(struct interface_stats));
            if (!new_list) {
                free(if_list);
                fclose(fp);
                return -1;
            }
            if_list = new_list;
        }

        if_list[if_count++] = iface;
    }

    fclose(fp);

    *interfaces = if_list;
    *count = if_count;
    return 0;
}

int read_tcp_stats(struct tcp_stats *stats)
{
    FILE *fp;
    char line[512];

    if (!stats) {
        return -1;
    }

    memset(stats, 0, sizeof(*stats));

    // Parse /proc/net/tcp (IPv4)
    fp = fopen(PROC_NET_TCP, "r");
    if (fp) {
        // Skip header
        fgets(line, sizeof(line), fp);

        // Parse each connection line
        while (fgets(line, sizeof(line), fp)) {
            unsigned int state;
            // State is the 4th field (after sl, local_address, rem_address)
            if (sscanf(line, "%*u: %*x:%*x %*x:%*x %x", &state) == 1) {
                switch (state) {
                case 0x01:
                    stats->established++;
                    break;
                case 0x02:
                    stats->syn_sent++;
                    break;
                case 0x03:
                    stats->syn_recv++;
                    break;
                case 0x04:
                    stats->fin_wait1++;
                    break;
                case 0x05:
                    stats->fin_wait2++;
                    break;
                case 0x06:
                    stats->time_wait++;
                    break;
                case 0x07:
                    stats->close++;
                    break;
                case 0x08:
                    stats->close_wait++;
                    break;
                case 0x09:
                    stats->last_ack++;
                    break;
                case 0x0A:
                    stats->listen++;
                    break;
                case 0x0B:
                    stats->closing++;
                    break;
                }
            }
        }
        fclose(fp);
    }

    // Parse /proc/net/tcp6 (IPv6)
    fp = fopen(PROC_NET_TCP6, "r");
    if (fp) {
        // Skip header
        fgets(line, sizeof(line), fp);

        // Parse each connection line
        while (fgets(line, sizeof(line), fp)) {
            unsigned int state;
            if (sscanf(line, "%*u: %*s %*s %x", &state) == 1) {
                switch (state) {
                case 0x01:
                    stats->established++;
                    break;
                case 0x02:
                    stats->syn_sent++;
                    break;
                case 0x03:
                    stats->syn_recv++;
                    break;
                case 0x04:
                    stats->fin_wait1++;
                    break;
                case 0x05:
                    stats->fin_wait2++;
                    break;
                case 0x06:
                    stats->time_wait++;
                    break;
                case 0x07:
                    stats->close++;
                    break;
                case 0x08:
                    stats->close_wait++;
                    break;
                case 0x09:
                    stats->last_ack++;
                    break;
                case 0x0A:
                    stats->listen++;
                    break;
                case 0x0B:
                    stats->closing++;
                    break;
                }
            }
        }
        fclose(fp);
    }

    return 0;
}

int read_tcp_retransmits(struct tcp_retransmit_stats *stats)
{
    FILE *fp;
    char line[512];
    char label[64];

    if (!stats) {
        return -1;
    }

    memset(stats, 0, sizeof(*stats));

    fp = fopen(PROC_NET_SNMP, "r");
    if (!fp) {
        fprintf(stderr, "ERROR: failed to open %s\n", PROC_NET_SNMP);
        return -1;
    }

    // Find the "Tcp:" data line (second line with "Tcp:" prefix)
    int found_header = 0;
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%63s", label) == 1 && strcmp(label, "Tcp:") == 0) {
            if (found_header) {
                // This is the data line
                // Parse fields: we want RetransSegs which is the 13th field
                unsigned long long fields[20];
                int ret = sscanf(
                    line, "Tcp: %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu %llu",
                    &fields[0], &fields[1], &fields[2], &fields[3], &fields[4], &fields[5],
                    &fields[6], &fields[7], &fields[8], &fields[9], &fields[10], &fields[11],
                    &fields[12]);
                if (ret >= 13) {
                    stats->retrans_segs = fields[12];
                }
                break;
            } else {
                found_header = 1;
            }
        }
    }

    fclose(fp);
    return 0;
}

void print_interface_stats_json(const struct interface_stats *iface, uint64_t timestamp)
{
    printf("{\"timestamp\":%lu,\"type\":\"net_interface\",\"interface\":\"%s\",\"data\":{\"rx_"
           "bytes\":%lu,\"rx_packets\":%lu,\"rx_errors\":%lu,\"rx_drops\":%lu,\"tx_bytes\":%lu,"
           "\"tx_packets\":%lu,\"tx_errors\":%lu,\"tx_drops\":%lu}}\n",
           timestamp, iface->name, iface->rx_bytes, iface->rx_packets, iface->rx_errors,
           iface->rx_drops, iface->tx_bytes, iface->tx_packets, iface->tx_errors, iface->tx_drops);
    fflush(stdout);
}

void print_tcp_stats_json(const struct tcp_stats *stats, uint64_t timestamp)
{
    printf("{\"timestamp\":%lu,\"type\":\"tcp_stats\",\"data\":{\"established\":%u,\"syn_sent\":%u,"
           "\"syn_recv\":%u,\"fin_wait1\":%u,\"fin_wait2\":%u,\"time_wait\":%u,\"close\":%u,"
           "\"close_wait\":%u,\"last_ack\":%u,\"listen\":%u,\"closing\":%u}}\n",
           timestamp, stats->established, stats->syn_sent, stats->syn_recv, stats->fin_wait1,
           stats->fin_wait2, stats->time_wait, stats->close, stats->close_wait, stats->last_ack,
           stats->listen, stats->closing);
    fflush(stdout);
}

void print_tcp_retransmit_json(const struct tcp_retransmit_stats *stats, uint64_t timestamp)
{
    printf("{\"timestamp\":%lu,\"type\":\"tcp_retransmits\",\"data\":{\"retrans_segs\":%lu}}\n",
           timestamp, stats->retrans_segs);
    fflush(stdout);
}

void free_interface_stats(struct interface_stats *interfaces, int count)
{
    (void)count; // Unused
    free(interfaces);
}
