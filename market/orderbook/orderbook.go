package orderbook

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/tent-of-trials/market/types"
)

type Config struct {
	MaxDepth       int
	PriceDecimals  int32
	VolumeDecimals int32
}

type OrderBook struct {
	mu           sync.RWMutex
	symbol       types.Symbol
	config       Config
	bids         []*types.Level
	asks         []*types.Level
	orders       map[string]*types.Order
	sequence     uint64
	updatedAt    time.Time
	closed       bool
	snapshotDir  string
	stopSnapshot chan struct{}
}

type snapshotData struct {
	Bids      []*types.Level          `json:"bids"`
	Asks      []*types.Level          `json:"asks"`
	Orders    map[string]*types.Order `json:"orders"`
	Sequence  uint64                  `json:"sequence"`
	Timestamp int64                   `json:"timestamp"`
	Checksum  string                  `json:"checksum"`
}

func NewOrderBook(symbol types.Symbol, config Config) *OrderBook {
	return &OrderBook{
		symbol:   symbol,
		config:   config,
		bids:     make([]*types.Level, 0, config.MaxDepth),
		asks:     make([]*types.Level, 0, config.MaxDepth),
		orders:   make(map[string]*types.Order),
		sequence: 0,
	}
}

func (ob *OrderBook) AddOrder(order *types.Order) ([]*types.Trade, error) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	if ob.closed {
		return nil, ErrBookClosed
	}

	if order.ID == "" {
		order.ID = uuid.New().String()
	}

	order.CreatedAt = time.Now()
	order.UpdatedAt = time.Now()
	order.Status = types.New

	ob.orders[order.ID] = order
	ob.sequence++

	level := &types.Level{
		Price:    order.Price,
		Quantity: order.RemainingQty,
		Count:    1,
	}

	if order.Side == types.Buy {
		ob.bids = insertLevel(ob.bids, level, true)
	} else {
		ob.asks = insertLevel(ob.asks, level, false)
	}

	ob.updatedAt = time.Now()
	return nil, nil
}

func (ob *OrderBook) CancelOrder(orderID string) error {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	if ob.closed {
		return ErrBookClosed
	}

	order, exists := ob.orders[orderID]
	if !exists {
		return ErrOrderNotFound
	}

	order.Status = types.Cancelled
	order.UpdatedAt = time.Now()
	delete(ob.orders, orderID)

	if order.Side == types.Buy {
		ob.bids = removeLevel(ob.bids, order.Price)
	} else {
		ob.asks = removeLevel(ob.asks, order.Price)
	}

	ob.updatedAt = time.Now()
	return nil
}

func (ob *OrderBook) GetBids() []*types.Level {
	ob.mu.RLock()
	defer ob.mu.RUnlock()

	result := make([]*types.Level, len(ob.bids))
	copy(result, ob.bids)
	return result
}

func (ob *OrderBook) GetAsks() []*types.Level {
	ob.mu.RLock()
	defer ob.mu.RUnlock()

	result := make([]*types.Level, len(ob.asks))
	copy(result, ob.asks)
	return result
}

func (ob *OrderBook) GetSnapshot() *types.DepthUpdate {
	ob.mu.RLock()
	defer ob.mu.RUnlock()

	bids := make([]types.Level, len(ob.bids))
	for i, l := range ob.bids {
		if l != nil {
			bids[i] = *l
		}
	}

	asks := make([]types.Level, len(ob.asks))
	for i, l := range ob.asks {
		if l != nil {
			asks[i] = *l
		}
	}

	return &types.DepthUpdate{
		Symbol:    ob.symbol,
		Bids:      bids,
		Asks:      asks,
		Timestamp: time.Now().UnixMilli(),
	}
}

func (ob *OrderBook) Snapshot() ([]byte, error) {
	ob.mu.RLock()
	defer ob.mu.RUnlock()

	sd := snapshotData{
		Bids:      ob.bids,
		Asks:      ob.asks,
		Orders:    ob.orders,
		Sequence:  ob.sequence,
		Timestamp: ob.updatedAt.UnixMilli(),
	}

	data, err := json.Marshal(sd)
	if err != nil {
		return nil, fmt.Errorf("marshal snapshot: %w", err)
	}

	h := sha256.Sum256(data)
	sd.Checksum = hex.EncodeToString(h[:])

	return json.Marshal(sd)
}

func (ob *OrderBook) Recover(data []byte) error {
	var sd snapshotData
	if err := json.Unmarshal(data, &sd); err != nil {
		return fmt.Errorf("unmarshal snapshot: %w", err)
	}

	storedChecksum := sd.Checksum
	sd.Checksum = ""

	verify, err := json.Marshal(sd)
	if err != nil {
		return fmt.Errorf("marshal for checksum: %w", err)
	}

	h := sha256.Sum256(verify)
	if hex.EncodeToString(h[:]) != storedChecksum {
		return ErrCorruptSnapshot
	}

	ob.mu.Lock()
	defer ob.mu.Unlock()

	ob.bids = sd.Bids
	ob.asks = sd.Asks
	ob.orders = sd.Orders
	ob.sequence = sd.Sequence
	ob.updatedAt = time.UnixMilli(sd.Timestamp)

	return nil
}

func (ob *OrderBook) Init(snapshotDir string) error {
	ob.snapshotDir = snapshotDir

	jsonPath := filepath.Join(snapshotDir, "orderbook_snapshot.json")
	shaPath := filepath.Join(snapshotDir, "orderbook_snapshot.sha256")

	if _, err := os.Stat(jsonPath); os.IsNotExist(err) {
		return nil
	}

	jsonData, err := os.ReadFile(jsonPath)
	if err != nil {
		return fmt.Errorf("read snapshot: %w", err)
	}

	shaData, err := os.ReadFile(shaPath)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("read checksum: %w", err)
	}

	expectedChecksum := strings.TrimSpace(string(shaData))
	actualChecksum := sha256.Sum256(jsonData)
	if hex.EncodeToString(actualChecksum[:]) != expectedChecksum {
		return ErrCorruptSnapshot
	}

	return ob.Recover(jsonData)
}

func (ob *OrderBook) StartSnapshotWriter() {
	ob.stopSnapshot = make(chan struct{})

	interval := snapshotInterval()
	go func() {
		ticker := time.NewTicker(interval)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				ob.writeSnapshotFile()
			case <-ob.stopSnapshot:
				return
			}
		}
	}()
}

func (ob *OrderBook) writeSnapshotFile() {
	data, err := ob.Snapshot()
	if err != nil {
		return
	}

	dir := ob.snapshotDir
	if dir == "" {
		dir = "data"
	}

	if err := os.MkdirAll(dir, 0755); err != nil {
		return
	}

	jsonPath := filepath.Join(dir, "orderbook_snapshot.json")
	shaPath := filepath.Join(dir, "orderbook_snapshot.sha256")

	if err := os.WriteFile(jsonPath, data, 0644); err != nil {
		return
	}

	h := sha256.Sum256(data)
	shaContent := []byte(hex.EncodeToString(h[:]) + "\n")
	_ = os.WriteFile(shaPath, shaContent, 0644)
}

func snapshotInterval() time.Duration {
	s := os.Getenv("OB_SNAPSHOT_INTERVAL_SECS")
	if s == "" {
		return 60 * time.Second
	}
	n, err := strconv.Atoi(s)
	if err != nil || n <= 0 {
		return 60 * time.Second
	}
	return time.Duration(n) * time.Second
}

func (ob *OrderBook) Close() {
	ob.mu.Lock()
	defer ob.mu.Unlock()
	ob.closed = true
	ob.bids = nil
	ob.asks = nil
	ob.orders = nil
	if ob.stopSnapshot != nil {
		close(ob.stopSnapshot)
		ob.stopSnapshot = nil
	}
}

var (
	ErrBookClosed      = &BookError{"order book is closed"}
	ErrOrderNotFound   = &BookError{"order not found"}
	ErrCorruptSnapshot = &BookError{"corrupt snapshot: checksum mismatch"}
)

type BookError struct {
	message string
}

func (e *BookError) Error() string {
	return e.message
}

func insertLevel(levels []*types.Level, level *types.Level, desc bool) []*types.Level {
	levels = append(levels, level)
	sort.Slice(levels, func(i, j int) bool {
		if desc {
			return levels[i].Price.GreaterThan(levels[j].Price)
		}
		return levels[i].Price.LessThan(levels[j].Price)
	})
	return levels
}

func removeLevel(levels []*types.Level, price decimal.Decimal) []*types.Level {
	for i, l := range levels {
		if l.Price.Equal(price) {
			return append(levels[:i], levels[i+1:]...)
		}
	}
	return levels
}
