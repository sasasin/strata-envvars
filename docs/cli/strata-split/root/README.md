# `strata-split-N`（全カード分割 engine）

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N はビルド時のカード数 2 / 3 / 4） |
| 主な実装 | `src/split/tools/sfnx.cpp`、`src/split/src/` |
| 起動元 | Strata Terminal の server。対応 engine package に含まれる場合に限り起動候補になります。 |
| 実行形態 | server との標準入力・標準出力プロトコルで動く engine subprocess |

## 役割

Qwen3.8-Flash-Next の全層を複数 GPU に分け、各 GPU が各層の一部を持つ方式で推論するネイティブ engine です。通常の layer split が層ごとに GPU を割り当てるのに対し、この engine は全層をカード間で分割します。GPU 間の中間値交換にはページ固定 host memory を使います（`strata_control/split_engine.py:250-270`、`src/split/CMakeLists.txt:1-11`）。

これは直接対話して使う汎用コマンドではありません。Terminal が実行設定を判定して engine を選び、`serve/server.py` が起動・通信します。ソースの parser は `--serve` を必須とし、通常の `--help` / `-h` は定義していません（`src/split/tools/sfnx.cpp:72-104`）。

## 基本的な使い方

Terminal から launch します。`--split-engine auto` は通常の既定値で、対応条件を満たす場合だけこの engine を選択します。利用可能な実行ファイルが package にない場合や条件に合わない場合は通常の layer split が使われます。

```sh
# 対応条件に合う環境では全カード分割を自動選択
strata launch --split-engine auto

# 判定にかかわらず全カード分割を要求
strata launch --split-engine on

# 全カード分割を使わず通常の layer split を使う
strata launch --split-engine off
```

`strata launch --split-engine` の値と保存方法は [`strata-terminal` の CLI 索引](../../../README.md)にある該当オプション文書を参照してください。Terminal が構成する engine 引数の例は、`--native MODEL.gguf --mtp DRAFT_DIR --draft-vocab VOCAB.bin --max-context N --spec 6 --lookup 15 --conversation-cache-mib 4096 --batch N --serve` 相当です。これらは server が自動生成する内部起動引数であり、手動起動用の一般的な CLI 例ではありません（`strata_control/split_engine.py:250-263`、`src/split/tools/sfnx.cpp:72-104`）。

## 実行モードと選択条件

| モード | 動作 |
| --- | --- |
| `auto`（既定） | 選択ルールを満たせば起動します。満たさないときは通常の layer split に移り、拒否理由は通常表示しません。 |
| `on` | 全カード分割を要求します。適用条件を満たさない場合は理由を含めて通常の layer split が選ばれます。AMD では未検証アーキテクチャも明示要求時の対象となり、engine 自身の kernel self-test を行います。 |
| `off` | 全カード分割を使いません。 |

モードは `strata launch --split-engine` の設定または run config から読み、環境変数 `STRATA_SPLIT_ENGINE` が設定されていればそちらを優先します。値 `on` / `1` / `true` / `yes` は有効、`off` / `0` / `false` / `no` は無効として扱い、その他の値は `auto` になります（`strata_control/split_engine.py:356-374,435-448`）。

主な適用条件は Linux、同じメーカー・同じ型と VRAM 容量の 2〜4 枚の GPU、対応アーキテクチャ、対応する GGUF 構造、全 routed expert が GPU メモリーに収まること、および利用可能な host RAM です。モデル形状は 48 層・512 experts の Qwen3.8-Flash-Next に限定されます。現在の通常判定は検証済みのカード数・アーキテクチャと最大 131072 context も条件にします（`strata_control/split_engine.py:176-247`）。

AMD の `auto` はさらに制限され、現行ルールでは `gfx1201` の 4 枚と所定の routed expert 型に限って自動選択します。`on` はこの AMD の自動選択ゲートを適用しません（`strata_control/split_engine.py:54-62,377-390`）。実行ファイル自体も CMake で `STRATA_SPLIT_CARDS` の 2 / 3 / 4 ごとに生成し、NVIDIA は単一 CUDA architecture、HIP は許可された architecture 群向けにビルドされます（`src/split/CMakeLists.txt:13-18,20-61,92-123`）。

## 主な動作と副作用

- 起動時に native GGUF、MTP draft layer、draft vocabulary を読み、engine と server protocol を初期化します。起動が完了すると標準出力へ `INFO` と `READY` を出し、標準入力から server の request line を受けます（`src/split/tools/sfnx.cpp:1040-1085`）。
- 推論時は単発の `GEN` と複数 slot の `BGEN` を扱います。画像用 `GENI` / `BGENI` は `--vision` 付きで起動した場合だけ受け付けます。生成結果・完了情報などは標準出力の protocol line として返します（`src/split/tools/sfnx.cpp:7-20,961-1003`）。
- Terminal は `parallel` または既定値から batch lane 数を決め、1〜8 の範囲に収めて `--batch` に渡します。engine 側も `--batch` を 1〜8 で検証します（`strata_control/split_engine.py:78-80,508-510`、`src/split/tools/sfnx.cpp:89-103`）。
- Terminal が engine 起動を拒否されたと判定した場合は通常の layer split の設定を維持します。split engine のプロセス起動・初期化が失敗した場合も、server は理由を表示し、通常 engine を起動します。設定ログがあれば split engine のログを `.split-engine` 付きの名前へ移そうとします（`strata_control/split_engine.py:435-512`、`serve/server.py:9107-9145`）。
- GPU memory、ページ固定 host memory、host RAM を使います。利用可能な RAM や各 GPU の空き VRAM が不足すると選択条件を満たさず、また読み込み中の例外は engine の `ERR` 出力と stderr の診断を伴う失敗になります（`strata_control/split_engine.py:238-247`、`src/split/tools/sfnx.cpp:1027-1077`）。

## 注意点

- CMake target は `strata-split-2`、`strata-split-3`、`strata-split-4` です。NVIDIA package 内では compute capability 付きの名前、AMD package 内では architecture 付きの名前で配置される場合があります。実際に使うファイルは Terminal が engine component folder から解決します（`src/split/CMakeLists.txt:92-97,116`、`strata_control/split_engine.py:493-497`）。
- CMake では Linux CUDA または Linux HIP 以外の構成では split engine を生成せず、必要な ggml CUDA headers がない場合も対象を skip します（`src/split/CMakeLists.txt:20-30`）。
- parser の必須条件は `--serve`、`--native`、`--mtp` です。未知の引数はエラーとなり、引数不足・不正値など parse 段階の失敗は stderr に `sfnx: ...` を出して status 2 で終了します。モデル読み込み後の致命的失敗は標準出力に `ERR ...`、stderr に診断を出し status 1 で終了します（`src/split/tools/sfnx.cpp:77-103,1030-1048,1051-1062`）。
- `strata-split` 独立の Release asset や全 platform の package 実体は、この文書では確認していません。engine package に同梱されているかは使用する配布物によります。索引側の Release 確認範囲は [`000_cli_tools.md`](../../000_cli_tools.md) を参照してください。

## 関連文書

- [CLI 索引と `strata-split` の option 文書一覧](../../../README.md)
- [全カード分割 engine の設計資料（Strata 同 revision）](https://github.com/Niko1221/Strata/blob/ffa80d73133ea5c548aefe57889a16e8085a938f/docs/SPLIT_ENGINE.md)
- [`strata-split` の配置・配布調査](../../000_cli_tools.md)

## 根拠

- Strata `src/split/tools/sfnx.cpp:65-104,961-1003,1027-1095` — parser、必須引数、protocol 処理、起動・エラー経路。
- Strata `src/split/CMakeLists.txt:13-30,92-123` — build 条件、カード数別 target、CUDA/HIP architecture。
- Strata `strata_control/split_engine.py:176-247,250-271,356-390,435-512` — 選択条件、Terminal が作る起動設定、mode precedence、fallback 条件。
- Strata `serve/server.py:9107-9145` — split engine 起動失敗時の通常 engine fallback。
