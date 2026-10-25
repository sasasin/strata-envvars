# `STRATA_METAL_STREAM`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有のソースコードで、外部 Metal/GPU ライブラリの挙動は含めない。

## 役割

Apple Metal engine が MoE expert 重みを GGUF 全体の Metal buffer として常駐させるか、expert 重みを SSD から必要に応じて読み込むかを選ぶ。streaming の場合も dense tensor は一度メモリへ読み込み、routed expert は expert arena の slot に読み込む。これは `metal/` の Metal engine の経路で使われる設定である。

## 値と判定

値は文字列全体で比較する。数値変換、trim、大文字小文字変換はしない。

| 環境変数 | 判定 |
|---|---|
| unset | 自動判定 |
| `1` | streaming を強制する |
| `0` | streaming を無効にし、GGUF を wrap する経路を選ぶ |
| 空文字、`true`、`false`、`01`、その他 | 自動判定（`1` / `0` と完全一致しない） |

自動判定では、GGUF 内の tensor byte 数を合計する。ただし `per_layer_token_embd.weight` は合計から除く。物理 RAM と Metal device の recommended working set を取得し、合計 byte 数に 12 GiB の余裕（prompt buffer、KV、draft layer 等）を足した値が resident cap 以下なら resident、超えるなら streaming とする。resident cap は `min(recommended working set, RAM - keep)`。`keep` は通常 `max(7 GB, RAM の 15%)`、RAM 64 GB 以上では `max(7 GB, RAM の 15%, RAM の 30%)` である。比較は `model_bytes + overhead <= resident_cap` である。

## 有効になる条件

- この判定は Metal decode window の初期化時に使われる。非 Metal engine の環境変数としては読まれない。
- 強制値 `1` は自動判定の fit 結果にかかわらず streaming を選ぶ。強制値 `0` は同様に resident 経路を選ぶ。後者でも、OS/GPU が必要なメモリを確保できることまでは保証しない。
- 自動判定の RAM / working set 取得には macOS の `sysctlbyname("hw.memsize", ...)` と Metal context の `recommended_working_set()` を使う。
- setup はモデルサイズと RAM から streaming 要否を判定し、生成する設定の `env` に `STRATA_METAL_STREAM` を `1` または `0` として書く。この設定を使う起動経路では engine の自動判定ではなく setup 側の選択が優先される。

## 実行時の詳細

`Window::init()` が GGUF を開き Metal context を作った後、`ExpertStream::wanted()` を呼び、その時点で `getenv()` の値を評価する。判定は static cache されないが、初期化後の同一 window は `stream_` に保存した選択を保持して使用する。したがって実行中に環境変数を変更しても既存 window の方式は切り替わらず、新しい window の初期化で改めて評価される。

streaming が選ばれると `ExpertStream` を開く。失敗時は初期化が失敗し、resident 経路への自動 fallback はない。streaming を選ばない場合は GGUF の memory map を `madvise(..., MADV_WILLNEED)` し、その領域を Metal buffer として wrap する。起動ログには `streamed from the SSD (experts)` または `wrapped` と表示される。

`docs/MAC.md` は `=1` を「pack が fit しても SSD stream」、`=0` を「stream しない」、未指定時をサイズによる既定判定として説明しており、コードの分岐と一致する。本調査では性能値を追加していない。

## 根拠

- `metal/src/engine/stream.cpp:27-30,33-48` — env の取得、完全一致判定、自動判定の tensor 集計と fit 判定。
- `metal/src/engine/arena_budget.h:75-97,135-142` — resident cap と 12 GiB overhead を含む fit の式。
- `metal/src/engine/window.cpp:409-436,560-563` — 初期化時の選択、streaming open / resident wrap の分岐、および起動ログ。
- `metal/setup_mac.py:166-182,648-674` — setup 側の容量判定と設定ファイルへの `1` / `0` 書き込み。
- `docs/MAC.md:183-200` — 利用者向けの既定と手動指定の説明。
