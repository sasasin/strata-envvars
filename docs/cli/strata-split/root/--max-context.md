# `strata-split-N --max-context`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（`N` は build 時のカード数） |
| オプション | `--max-context` |
| 別名 | なし |
| 値 | 10 進整数として `std::stoi` で読み取るコンテキスト長（token 数） |

## 役割

sFNX エンジンが扱うコンテキスト長の上限を指定します。起動時にモデルの rotary がカバーする長さと照合され、Engine のコンテキスト領域の確保にも使われます。要求ごとの prompt と生成長もこの値を超えられません（`src/split/tools/sfnx.cpp:85, 991`、`src/split/src/engine.cu:31, 49-53, 71-80`）。

## 使い方

```sh
strata-split-2 --serve --native MODEL.gguf --mtp RT_DIR --max-context 32768
```

`--serve`、`--native`、`--mtp` はこの実行ファイルの必須起動引数です。`strata-split-N` は build 時のカード数を含む実行ファイル名です（`src/split/tools/sfnx.cpp:4-5, 81-102`）。

## 値と既定値

- 省略時は `262144` です（`src/split/tools/sfnx.cpp:65-68`）。
- 値の取得後、`std::stoi` で `int` に変換します。値がない場合は `--max-context needs a value`、整数変換に失敗した場合は標準例外になります。変換位置の終端を検査するコードはないため、`std::stoi` が整数部分を読める文字列では後続文字が無視され得ます（`src/split/tools/sfnx.cpp:75-86`）。同じオプションを複数回指定すると、走査順で最後に変換された値が残ります（同: `75-86`）。
- `--max-context` 自体に正数・最小値の明示 validation はありません。Engine 初期化はモデル rotary の上限を超える場合を拒否しますが、0 以下をこの比較だけで拒否するものではありません。正の長さを指定してください（`src/split/src/engine.cu:31, 48-53`）。
- モデル GGUF の `context_length` はモデル読込時に `1..INT32_MAX` と検査されます（`src/split/src/model.cpp:1296-1300`）。

## 実行時の動作

parser の値は起動時に `fnx::Engine` のコンストラクタへ渡されます（`src/split/tools/sfnx.cpp:1055-1059`）。Engine はモデルの rotary 設定から使用可能な上限を決め、`--max-context` がその上限を超える場合は例外にします。通常はモデルの学習済み長が上限です。`--rope-scale`、モデル内 YaRN 設定、および `FNX_YARN_ORIG_CTX` が有効な場合は rotary の上限が変わります。モデル自身が YaRN factor を持つとき、異なる `FNX_ROPE_SCALE` を指定するのもエラーです（`src/split/src/engine.cu:37-60`; `src/split/src/rope.hpp:82-113`）。

指定長から全コンテキスト分の K/V pool page 数を計算し、GPU に pool を確保します（`src/split/src/engine.cu:70-80, 350-371`）。上限を大きくすると必要な GPU 領域も増え、確保に失敗すれば起動時エラーになります。モデルの arena が有効な場合は空き VRAM に合わせて初期 page 数を抑え、`FNX_ARENA_BASE_PAGES` があればその初期値も検査・指定します（同: `317-345`）。カードごとの query score 領域も `max_ctx / 4` に比例して確保されます（同: `214-217`）。

## 適用条件と副作用

- `--max-context` は sFNX engine の起動時設定です。Terminal 側から起動する場合は起動引数を組み立てる側の挙動が関わりますが、この文書では `strata-split-N` 自身の parser と処理を対象にしています。
- 要求受付時に `prompt token 数 + max_new + 8` が指定長を超える要求は拒否されます。応答行 `ERR <コマンド>: prompt + max_new exceed the context` を出し、その要求を処理せずサーバーループを継続します（`src/split/tools/sfnx.cpp:988-996`）。さらに Engine 側も prompt 読込、状態復元、生成 window の各位置が上限内か確認します（`src/split/src/session.cpp:154-158`; `src/split/src/engine_common.cu:593-600, 777-783, 898-904, 1089-1094`）。
- 起動成功時は stderr の `sfnx: loaded ... context <値> ...` と stdout の `READY <値> stop` に設定値が表示されます（`src/split/tools/sfnx.cpp:1068-1083`）。

## 出力とエラー

- 引数不足や `std::stoi` の変換例外など parser 段階のエラーは `sfnx: <理由>` を stderr に出し、終了コード 2 になります（`src/split/tools/sfnx.cpp:77-79, 85, 1040-1049`）。
- rotary の上限超過や Engine 初期化中の確保失敗など、モデル読込後の初期化エラーは stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出して終了コード 1 になります（`src/split/tools/sfnx.cpp:1027-1035, 1050-1061`）。
- prompt と生成長の合計が大きすぎる要求は前述のとおり `ERR` 行を返しますが、プロセス終了にはなりません（同: `988-996`）。

## 根拠

- parser、既定値、必須引数、変換: `src/split/tools/sfnx.cpp:65-105`
- Engine への値の引き渡し: `src/split/tools/sfnx.cpp:1040-1061`
- rotary 上限、YaRN の適用: `src/split/src/engine.cu:31-60`; `src/split/src/rope.hpp:82-113`
- context 長に応じた pool page と領域、arena との調整: `src/split/src/engine.cu:70-80, 214-217, 317-371`
- 要求時の長さ検査と Engine の上限検査: `src/split/tools/sfnx.cpp:988-996`; `src/split/src/session.cpp:154-158`; `src/split/src/engine_common.cu:593-600, 777-783, 898-904, 1089-1094`
- 起動時エラー、終了コード、READY/loaded 表示: `src/split/tools/sfnx.cpp:1027-1083`
