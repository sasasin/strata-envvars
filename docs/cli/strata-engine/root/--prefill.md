# `--prefill`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（トップレベル引数） |
| オプション | `--prefill CHUNK` |
| 別名 | なし |
| 値 | 正の token 数、`auto`、`auto:16384`、`auto:32768` など。`CHUNK` は prompt をまとめて処理する token 数。 |

## 役割

prompt の先頭から最終 token の直前までを、指定 token 数ずつまとめて処理するバッチ prefill を有効にします。エンジンの help は `--native` が必要と説明しています。native pack の複数 token 入力では `--prefill` が必須です（`src/program/generate.cpp:960-962,3754-3759`）。

## 使い方

```sh
strata --native model.gguf --pack experts --tokens 1,2,3 --prefill 2048
strata --native model.gguf --pack experts --tokens 1,2,3 --prefill auto
```

これはエンジン引数の例です。`--native` と `--pack` の具体的なファイル構成はモデルに依存します。

## 値と既定値

- 省略時は `prefill_chunk = 0` です。この値ではバッチ prompt path は起動せず、token ごとの path が使われます（`src/program/generate.cpp:620-621,15711-15713`）。
- 数値は `std::atoll` で変換され、正数は chunk の token 数になります。明示した数値に正の範囲検証はありません。0、負数、数値に変換できない値は 0 相当となり、バッチ path を有効にしません（`src/program/generate.cpp:2574-2582,15712`）。
- `auto` は標準で上限 8192 token の自動選択です。`auto:N` または `STRATA_PREFILL_AUTO_MAX` で上限を拡張でき、値は 8192 / 16384 / 32768 のいずれかに丸められます。たとえば指定値が 16384 以上 32768 未満なら 16384、32768 以上なら 32768 です。それより小さい値・不正値は 8192 になります（`src/program/generate.cpp:2576-2582`）。
- 重複指定は parser が順に値を代入するため後の指定が残ります（parser loop と `--prefill` 分岐: `src/program/generate.cpp:2390-2423,2574-2600`）。

## 実行時の動作

値が正で prompt が複数 token の場合に prefill path を初期化します。cache から buffer を借りる通常経路では、自動指定は cache に収まる最大 chunk を探し、明示数値は必要に応じて小さくして fit を調べます（`src/program/generate.cpp:15711-15718,4805-4815`）。`auto` の実際の選択値は標準エラーに `strata generate: prompt chunk auto: ... tokens` と表示されます（`src/program/generate.cpp:15752-15755`）。

自動指定でも、借用を無効にする `--no-prefill-borrow` または expert profile がない場合、起動時に `auto` を解除して chunk を 2048 にします（`src/program/generate.cpp:3164-3167`）。serve の cache 経路では、借用可能な chunk がない場合に 1024 token に fallback する分岐もあります（`src/program/generate.cpp:8693-8709`）。明示値が固定バッファとして cache に収まらない serve の layer split は、各 stage が独自 buffer を確保する fallback に進みます（`src/program/generate.cpp:8695-8706`）。

## 適用条件と副作用

- このオプションは native prompt path に対する設定です。native pack で複数 token を処理する場合、`--native`、`--spec` が 2 以上、正の `--prefill` が揃わないと標準エラーに要件を表示し終了コード 2 で終了します（`src/program/generate.cpp:3754-3759`）。
- Windows HIP build で bare `--prefill auto` を指定した場合は、自動 chunk を上限 6144 に抑えます。指定 chunk はこの上限で変更せず、8192 以上なら既知の commit charge 問題について警告します（`src/program/generate.cpp:2583-2598`; 上限条件: `include/strata/platform/host_limits.hpp:20-29`）。
- Linux HIP build の gfx12 では、bare `auto` の上限・選択値を 16384 に引き上げ、標準エラーに通知します。`STRATA_GFX12_CHUNK=0` または `STRATA_GFX12_DEFAULTS=0` ならこの引き上げを抑止します。明示数値、`auto:N`、`STRATA_PREFILL_AUTO_MAX` を使った指定には適用しません（`src/program/generate.cpp:2856-2873`）。
- positive chunk では prompt 用 GPU buffer を確保し、profile/cache 条件によっては expert cache の末尾 slot を一時借用して prompt 処理後に戻します。借用不能時は独自 buffer を使うため、VRAM の空きが足りないと初期化に失敗し得ます（`src/program/generate.cpp:15758-15787`）。

## 出力とエラー

native pack に必要な指定が不足すると stderr に必要条件を出して終了コード 2 です（`src/program/generate.cpp:3754-3759`）。prefill buffer 初期化が失敗した場合はエラー文字列を stderr に出して終了コード 1 です（`src/program/generate.cpp:15781-15789`）。値自体の一般的な範囲エラーは parser にありません。未知のオプションは `unknown argument` と usage を stderr に出し終了コード 2 ですが、これは未認識の引数に対する共通経路です（`src/program/generate.cpp:2788-2793`）。

## 根拠

- `src/program/generate.cpp:620-634,960-962` — chunk 状態、既定値、help 表記。
- `src/program/generate.cpp:2574-2600` — parser、数値変換、自動上限、Windows HIP 条件。
- `src/program/generate.cpp:2824-2834,2856-2873` — Windows gfx1151 と Linux gfx12 の自動上限調整。
- `src/program/generate.cpp:3164-3167,3754-3759` — `auto` fallback と native pack の要件。
- `src/program/generate.cpp:4805-4815,8693-8709,15711-15789` — fit 選択、serve fallback、実際の prefill 初期化。
- [`docs/cli/README.md`](../../README.md) の `strata-engine` 節 — オプション文書の tool ID、コマンド scope、配置。

調査範囲は索引が指定する CMake 製ネイティブエンジンの `src/program/generate.cpp` parser とその呼び出し経路です。ビルド済み CLI の help は実行せず、Release artifact や全 backend の実機挙動は確認していません。
