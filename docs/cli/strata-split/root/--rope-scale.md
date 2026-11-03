# `--rope-scale`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（`N` は 2 / 3 / 4 の build target） |
| オプション | `--rope-scale` |
| 別名 | なし |
| 値 | 有限な数値。`1` または `1` より大きい値 |

## 役割

全カード分割 engine の rotary position embedding に YaRN scaling を設定します。値 `S > 1` は、モデルの学習済み context 長を基準に rotary を拡張し、engine が受け付ける context 上限を通常は `学習済み長 × S` にします。設定は engine 起動時に適用され、生成リクエスト単位では切り替わりません。

## 使い方

```sh
strata-split-2 --serve --native model.gguf --mtp runtime-dir --rope-scale 4
```

`strata-split-N` の名前はカード数と build に応じます。`--serve` と `--native`、`--mtp` は起動に必要な引数です。`--rope-scale` は値を一つ消費します。

## 値と既定値

- オプション自体に数値型の parser はなく、次の argv 要素を文字列として受け取ります。値が欠けると `--rope-scale needs a value` になります（`src/split/tools/sfnx.cpp:72-79,91-92`）。
- parser 後に環境変数 `FNX_ROPE_SCALE` として数値検査されます。有限な数値表記を受け付け、`1` は scaling 無効、`1` より大きい値は scaling 有効です。`1` 未満、非数値、無限大、NaN は拒否され、上限値はコード上定義されていません（`src/split/tools/sfnx.cpp:103`; `src/split/src/engine_common.cu:1001-1008`; `src/split/src/env.hpp:24-30,42-48`）。
- 省略時はこの option による環境変数設定は行いません。環境変数も無ければ、GGUF の YaRN metadata がある場合はその設定を使い、無ければ未スケールです（`src/split/src/rope.hpp:82-97`; `src/split/src/engine.cu:48-57`）。
- 既に `FNX_ROPE_SCALE` が設定されている場合、option の値と文字列が完全一致しなければエラーです。数値として等しくても `4` と `4.0` は不一致になります。同じ値の繰り返し指定は通りますが、異なる値を重ねて指定すると後の指定で上書きされず不一致エラーになります（`src/split/tools/sfnx.cpp:91-96`）。

## 実行時の動作

値は `FNX_ROPE_SCALE` に設定され、engine 初期化時に `rope_scale()` で再検証されて `choose_rope()` に渡ります。モデル側に YaRN factor がある場合、option の値（`1` は無効値 `0` として扱われる）がモデル factor と異なると拒否されます。モデル自身が YaRN を宣言している場合は option 省略でその scaling が使われます（`src/split/src/engine_common.cu:1001-1008`; `src/split/src/rope.hpp:82-97`）。

有効な場合、モデルの `original_context_length` があればそれを、なければ `context_length` を scaling の基準長として選びます。`--max-context` で要求する最大長が rotary の上限を超えると engine 初期化に失敗します。上限は `max(学習済み長, 基準長 × S)` で、モデルがすでに拡張済み長を `context_length` として記録しているケースを扱います（`src/split/src/rope.hpp:99-113`; `src/split/src/engine.cu:48-53`; `src/split/src/model.cpp:1296-1306`）。

YaRN は rotary の周波数帯を補間し、振幅係数も設定します。そのため要求 context が学習済み長以内でも rotary 値は変化します。その場合は stderr に「長さの拡張に必要ない範囲でも scaling が rotary を変える」という注記が出ます（`src/split/src/rope.hpp:41-66`; `src/split/src/engine.cu:54-60`）。

## 適用条件と副作用

- `--rope-scale` は起動時 parser でのみ処理され、engine が初期化される前に環境変数を変更します。engine はモデルを読み込んだ後に scaling と要求 context の整合性を判定します（`src/split/tools/sfnx.cpp:91-104,1055-1060`; `src/split/src/engine.cu:37-55`）。
- GGUF に YaRN factor がある場合は option 値と一致が必要です。sFNX が追従しない rotary metadata はモデル読み込み時に拒否されるため、`--rope-scale` で回避できません（`src/split/src/rope.hpp:88-90`; `src/split/src/rope_gguf.hpp:25-57`）。
- 有効な `FNX_YARN_ORIG_CTX` が同時にある場合は基準長の指定にも使われます。モデル metadata に original context があれば値の一致が必要で、metadata が無い場合も学習済み長を超える指定は拒否されます（`src/split/src/engine.cu:41-48`; `src/split/src/rope.hpp:99-109`）。
- scale やモデルの rotary base / 基準長から有効な YaRN 周波数帯を作れない場合も engine 初期化で例外になります（`src/split/src/rope.hpp:47-66`）。

## 出力とエラー

引数不足、環境変数との文字列不一致、不正な scale、必須引数不足など parser 段階の例外は stderr に `sfnx: <理由>` と出て終了コード 2 になります（`src/split/tools/sfnx.cpp:78,91-104,1040-1049`）。モデル読み込み後の context 上限超過や scaling の不整合は stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` を出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1027-1035,1050-1061`）。scaling が有効なときは選ばれた factor、基準長、周波数帯などが stderr に記録されます（`src/split/src/engine.cu:54-60`）。

## 根拠

- parser と `FNX_ROPE_SCALE` 設定: `src/split/tools/sfnx.cpp:72-104`
- 数値形式と scale 条件: `src/split/src/env.hpp:24-30`; `src/split/src/engine_common.cu:1001-1008`
- モデル設定との選択・context 上限: `src/split/src/rope.hpp:82-113`; `src/split/src/engine.cu:37-60`
- YaRN 計算と拒否条件: `src/split/src/rope.hpp:41-66`
- モデル metadata の読み込みと制約: `src/split/src/model.cpp:1294-1306`; `src/split/src/rope_gguf.hpp:25-57`
- 起動時のエラー出力: `src/split/tools/sfnx.cpp:1027-1061`

調査は指定 revision の Strata ソースに基づきます。実機 GPU での起動、配布 package の実同梱確認、各モデルでの数値範囲の実測は行っていません。
