# `--prompt-len`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling` のトップレベル呼び出し（root） |
| オプション | `--prompt-len` |
| 別名 | なし |
| 値 | 整数 `N`。parser は `std::atoi` で変換し、明示的な範囲検証はしない |

## 役割

`--bench` モードで各並列 slot に与える合成 prompt の token 数を指定する。通常の生成、serve、selfcheck などで prompt 入力を指定するオプションではない。

## 使い方

```sh
strata-inkling --bench --native ./model.strata --prompt-len 512
```

`--native` には利用するモデルファイルまたはモデルディレクトリを指定する。ベンチモードは `--bench` で選択する。

## 値と既定値

- `--prompt-len` を省略した場合は `64`。生成長の既定値は `--gen` の `32`（この文書の対象外）。（`engine/src/inkling2/ink_main.cpp:376`）
- 値は `std::atoi` で整数化される。数値として解釈できない文字列や空文字列は `atoi` の結果 `0` となり、負数も parser では拒否されない。複数回指定した場合は、引数走査中に代入される最後の値が残る。（`engine/src/inkling2/ink_main.cpp:379-384,478-479`）
- オプションの後に値がない場合、`next()` が `missing value after --prompt-len` を stderr に出して終了コード `2` で終了する。（`engine/src/inkling2/ink_main.cpp:381-384,478-479`）

## 実行時の動作

値はベンチ引数 `bench_prompt` に格納され、`--bench` が選択されたとき `cmd_bench` に渡される。`--bench` がなければこの値はベンチ実行に使われない。モード判定では `mode_bench` の分岐が serve 実行より先に処理されるため、`--bench` と `--serve` の両方を指定した場合もベンチ経路が選ばれる。（`engine/src/inkling2/ink_main.cpp:394-395,544-550`）

ベンチはモデルを開いて backend を初期化した後、指定長の合成 token 列を `--chunk` ごとに分割して prefill する。各 token ID は slot ごとに生成され、実 prompt のテキストや tokenization は使わない。`--parallel` の slot 数ぶん同じ prompt 長を処理し、表示する prefill throughput の分子は `parallel × prompt_len`。（`engine/src/inkling2/ink_main.cpp:130-145,158-185,244-248`）

## 適用条件と副作用

- `prompt_len + gen_len` が設定済み `max_ctx` を超えると、backend 初期化前にベンチ用 `max_ctx` を `prompt_len + gen_len + 16` に広げる。ただし backend が報告する実効 context 長を越えられる保証にはならない。（`engine/src/inkling2/ink_main.cpp:137-145`）
- backend の実効 context 長が正ならそれを上限として使い、そうでなければ設定値を使う。prompt 長が実効上限以上なら stderr に clamp 警告を出し、`max(1, eff_ctx - 1)` に補正する。続いて生成長も残り context に収まるよう clamp する。（`engine/src/inkling2/ink_main.cpp:147-157`）
- `--parallel` は slot 数、`--chunk` は prefill 分割幅に関与する。prompt 長は各 slot の位置 0 から指定長までの処理に使われる。（`engine/src/inkling2/ink_main.cpp:158-185`）
- parser は 0 や負数を検証・補正しない。ソース上、prefill loop は `p0 < prompt_len` の条件で実行され、負数では loop が回らない。続く decode は `prompt_len` を開始位置として使用するため、0 以下を通常の有効値として扱えるとは確認できない。backend 側の最終的な応答は backend 実装・実行条件に依存し、この調査では実行していない。（`engine/src/inkling2/ink_main.cpp:171-185,197-230`）

## 出力とエラー

- 正常終了時は stdout に `[bench]` で始まる backend、形式、parallel 数、prompt/gen 長、prefill/decode throughput と所要時間を表示し、終了コード `0` を返す。（`engine/src/inkling2/ink_main.cpp:243-249`）
- 指定長が実効 context 以上の場合は stderr に `[bench] clamping prompt_len ...` を出す。値が不正な形式でも `atoi` による値変換後に専用エラーはなく、値の範囲によっては backend 処理で失敗し得る。（`engine/src/inkling2/ink_main.cpp:147-150,478-479`）
- モデルを開けない場合は `open: ...`、backend 初期化失敗は `init: ...`、prefill/decode の失敗はそれぞれ `bench prefill err: ...` / `bench decode err: ...` を stderr に出して終了コード `1` を返す。（`engine/src/inkling2/ink_main.cpp:130-145,181-184,216-219,230-232`）

## 根拠

- `engine/src/inkling2/ink_main.cpp:376,379-384,478-479` — 既定値、引数値の取得、`atoi` 変換、値欠落時のエラー。
- `engine/src/inkling2/ink_main.cpp:394-395,544-550` — `--bench` のモード選択とベンチ実行への引き渡し。
- `engine/src/inkling2/ink_main.cpp:130-165,171-185,243-249` — context 調整、合成 prompt の prefill、throughput 出力。
- `engine/src/inkling2/ink_main.cpp:147-157,197-230` — 実効 context による補正と decode 位置の使用。
- 索引上の scope: [`docs/cli/README.md`](../../README.md) の `strata-inkling`（トップレベル）節。
