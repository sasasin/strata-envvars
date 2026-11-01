# `--context`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | macOS の `setup.py` → `metal/setup_mac.py` |
| オプション | `--context` |
| 別名 | なし |
| 値 | 10 進整数（`argparse` の `type=int`）。setup parser に範囲指定なし |

## 役割

Apple Silicon の Metal 用 setup が作るモデル実行設定のコンテキスト容量を指定する。setup が自動推奨する値を使わず、指定値を生成 engine 引数 `--max-context` に渡す。

## 使い方

macOS で Strata ソース checkout のルートから実行する例:

```sh
./setup.sh --context 32768 --no-start
```

`setup.sh` は引数を `setup.py` に渡し、macOS かつ Control installer でない場合、`setup.py` は受け取った argv を `metal/setup_mac.py` にそのまま委譲する（`setup.sh:76`、`setup.py:9068-9069`、`setup.py:7703-7707`）。

## 値と既定値

- 省略時は Mac の unified memory が 96 GB 未満なら `32768`、96 GB 以上なら `65536`（`strata_control/mac_fit.py:180-181`）。
- 指定値は `int` に変換される。数値でない値は `argparse` が拒否する。setup parser 自体には choices や正の範囲チェックがない（`metal/setup_mac.py:327-334`）。
- 実装は `a.context or recommend_context(...)` を使うため、`0` は未指定と同じく推奨値へ置き換わる。負数は truthy のため保持される（`metal/setup_mac.py:411`）。
- 推奨値一覧は `8192, 32768, 65536, 131072` だが、これは選択肢 UI の一覧であり、`--context` の受理範囲を制限するものではない（`strata_control/mac_fit.py:61`、`metal/setup_mac.py:333`）。
- 指定値が `32768` を超えると、テスト済み上限が `32768` である旨を表示するが、値は変更せず継続する（`strata_control/mac_fit.py:68`、`metal/setup_mac.py:412-414`）。

## 実行時の動作

通常の setup 経路では、値は `engine_args(..., ctx, ...)` に渡り、設定 JSON の engine 引数列に `--max-context <値>` として記録される。Metal 側はこの engine 設定も生成する（`metal/setup_mac.py:542-560`、`strata_control/mac_fit.py:190-205`）。このため値はモデル準備の容量値として保持され、起動する engine の context/KV state capacity に使われる。setup の完了後は、生成された設定または起動スクリプトでモデルを起動する（`metal/setup_mac.py:302-323`、`metal/setup_mac.py:564-570`）。

適用されるのは、macOS 上で `STRATA_CONTROL_INSTALL=1` を設定せず `setup.py` / `setup.sh` を実行し、モデル設定を作成する経路である。既存 Metal 設定があり、`--setup`、`--model`、`--check`、`--no-start`、`--update`、`--build` のいずれも指定されない通常の再起動経路は既存設定を起動して早期 return するため、ここで `--context` を渡しても既存設定は変更されない（`setup.py:82`、`setup.py:9068-9069`、`metal/setup_mac.py:369-371`）。`--check` は設定生成前に終了し、`--update` もモデル設定生成より前に終了する（`metal/setup_mac.py:382-383`、`metal/setup_mac.py:435-448`）。

## 適用条件と副作用

- `--context` 自体はファイル・ネットワーク操作を行わないが、setup の通常処理は engine build、モデル取得・準備、設定 JSON と起動スクリプトの作成を行う。`--no-start` は設定作成後の engine/server 起動を抑える（`metal/setup_mac.py:428-570`）。
- 32768 を超える指定値は受け入れて設定に保持されるものの、ソース中の案内では Mac での測定上限は 32768 とされる。性能・メモリ適合性はこのオプションで検証・保証されない（`metal/setup_mac.py:412-414`、`strata_control/mac_fit.py:68`）。
- Mac setup parser の `parse_known_args` は未知の引数を `not used on a Mac: ...` と警告して続行する。これは `--context` の値検証とは別の挙動（`metal/setup_mac.py:356-358`）。

## 出力とエラー

setup は選択した context を `S.ok` の行で表示する。値が `32768` を超える場合は前述の測定範囲に関する案内も出す（`metal/setup_mac.py:412-414`）。

setup parser は負数や非常に大きい整数を拒否しない。生成された設定で通常の Strata engine を起動すると、`src/program/generate.cpp` は `--max-context` を整数として読み、値が `0` 以下、または `2^31 - 8` より大きい場合に stderr へエラーを出して終了コード `2` を返す。また、prompt と生成分を指定 context に収められない場合も終了コード `2` となる（`src/program/generate.cpp:3032`、`3918-3926`、`4650-4653`）。setup に `--no-start` を付けた場合は engine を起動しないため、こうした engine 側の検査はその場では行われない。

## 根拠

- macOS 委譲条件と argv 転送: `setup.py:82`、`setup.py:7703-7707`、`setup.py:9068-9069`。POSIX wrapper: `setup.sh:76`。
- option parser、整数変換、未知引数処理、値選択・案内: `metal/setup_mac.py:327-358`、`metal/setup_mac.py:411-414`。
- 推奨値とテスト済み context: `strata_control/mac_fit.py:61`、`strata_control/mac_fit.py:68`、`strata_control/mac_fit.py:180-181`。
- engine 引数・設定生成・起動経路: `strata_control/mac_fit.py:190-205`、`metal/setup_mac.py:542-570`、`metal/setup_mac.py:302-323`。
- 下流 engine の値検査: Metal build も `src/program/generate.cpp` を `strata` として build する（`metal/CMakeLists.txt:129`）。parser と検査は `src/program/generate.cpp:3032`、`src/program/generate.cpp:3918-3926`、`src/program/generate.cpp:4650-4653`。

調査範囲は上記 checkout のソースです。同一 revision の macOS 実機での CLI 実行や Release 配布物との照合は行っていません。
