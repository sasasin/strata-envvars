# `FNX_PEER_PARTS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

AMD/HIP 版 `strata-split` で、peer push が使えるときに、どのデータ交換経路を peer memory に置くかをビットで選びます。bit 0 (`1`) は decode window の和、bit 1 (`2`) は attention partial の merge です。既定値 `3` は両方を選びます。この変数は通常の Strata engine や NVIDIA CUDA 版では読み取られません。

## 値と判定

`env_int("FNX_PEER_PARTS", 3)` が環境値全体を符号付き base-10 `long long` として読み、結果を `int` に cast します。unset は `3`、設定済みの空文字・空白・数字以外の文字を含む値・`long long` の範囲外は無効で、起動時エラーになります。先頭の `+` / `-` は許され、末尾の文字は無視されません。値に範囲制限や clamp はなく、後段は `peer_parts & 1` と `peer_parts & 2` だけを検査します。

| 値 | 選ばれる部分（peer push が有効な場合） |
| --- | --- |
| unset | `3` と同じ。両方 |
| `0` | どちらも選ばない |
| `1` | window sums |
| `2` | attention merge |
| `3` | 両方 |
| 他の整数 | bit 0 / bit 1 の有無で選択。例: `4` はどちらも選ばず、`5` は window sums のみ |

`-1` のような負値も拒否されず `int` に変換された後、同じ下位ビット判定を受けます。`long long` で表せるが `int` で表せない値の cast 結果は C++ の処理系依存なので、移植可能な設定値としては使えません。

## 有効になる条件

- Strata が Linux HIP backend で `STRATA_BUILD_SPLIT=ON` として構築した `strata-split` を起動していること。通常 engine と CUDA split build にはこの読み取りがありません。
- AMD peer push が `FNX_PEER` の判定と起動時 probe を通じて有効になっていること。`FNX_PEER=0` または probe 失敗時は host-memory exchange が使われ、`FNX_PEER_PARTS` の選択は実動作に反映されません。ただし HIP build では値の parse 自体は peer 判定後に常に行われます。
- bit 0 の window-sum push はさらに `FNX_ONEHOP` が有効で fp16 ring 経路である必要があります。`FNX_ONEHOP=0` または fp32 ring では peer mailbox を確保してもその push kernel は選ばれません。
- bit 1 の attention merge は `FNX_ONEHOP` が有効なときに one-hop merge kernel が使われます。peer push が無効なら receive buffer は host memory のままです。

## 実行時の詳細

値は `Engine` 構築時に一度読み込まれ、キャッシュされます。後からプロセス環境を書き換えても再評価されません。CLI 引数や設定ファイルによる上書きはこの実装にありません。server 起動時には split engine 子プロセスが環境付きで起動されます。

peer push が有効な場合、bit 0 は各 card の `Ring.pk` mailbox を fine-grained device memory に確保します。window-sum kernel はこの mailbox を peer 側へ書き込み、その後自 card の mailbox から値を読みます。bit 1 は attention ring の受信領域を同じ種類の device allocation にし、one-hop merge kernel が各 card の受信領域へ partial を書きます。選択されない領域は pinned host-memory exchange 用です。

peer 判定の結果は `fnx: Peer push between the cards is on (...)` または失敗理由を含む host exchange の行として stderr に出ます。peer push が有効なら続けて `fnx: peer push: ... pushed into the peers' memory` の行が出て、選んだ部分名を示します。両 bit が 0 でも peer push 判定自体は有効のままで、この行は部分名なしで出ます。設定値が不正なら `env_int` が `FNX_PEER_PARTS: '<値>' is not a whole number` を例外にし、エンジンは stderr に `sfnx: failed: ...` を出して失敗します。サーバーが split engine を起動中に検出した失敗は、通常の layer split に fallback します。

## 根拠

- `src/split/src/engine.cu:81-105` — AMD peer 判定、`FNX_PEER_PARTS` の既定値 3 による読み取りとログ。
- `src/split/src/env.hpp:15-22,33-40` — 符号付き十進整数の全体 parse、空文字・不正値・範囲外の拒否。
- `src/split/src/engine.cu:245-270` — bit ごとの mailbox 確保、host-memory fallback、`FNX_ONEHOP` と fp32 条件。
- `src/split/src/kernels.cu:976-1004,1388-1402,1580-1595` — window-sum の peer push dispatch と attention merge dispatch。
- `src/split/src/kernels.cu:700-748` — one-hop attention merge が各 card の受信 buffer に書き込む処理。
- `src/split/src/engine.cu:266-273` — one-hop / fp32 ring 条件。
- `src/split/CMakeLists.txt:20-26,64-80,92-109` — split build の HIP/CUDA 条件と HIP compile 定義。
- `src/split/tools/sfnx.cpp:1040-1061` — Engine 構築例外の失敗経路。
- `serve/server.py:9107-9143` — split engine の起動失敗時の通常 engine fallback。
