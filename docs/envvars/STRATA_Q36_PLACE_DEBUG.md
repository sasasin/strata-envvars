# `STRATA_Q36_PLACE_DEBUG`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Qwen3.6-35B-A3B 用エンジンが prefill chunk を自動選択するとき、chunk 選択に使う VRAM と expert サイズの値を stderr に表示する診断フックです。この変数は chunk の選択条件や expert 配置を変えません。名前に `PLACE` を含みますが、この参照箇所で出すのは「chunk rule」の情報で、expert placement 自体の追加ログではありません。

## 値と判定

値は parse されず、`std::getenv("STRATA_Q36_PLACE_DEBUG")` が null かどうかだけを判定します。

| 環境変数の状態 | 診断行 |
|---|---|
| unset | 出さない |
| 空文字を含め、何らかの値が設定されている | 出す |

`0`、`false`、その他の文字列も、設定されていれば同じ扱いです。大文字小文字、数値変換、値域チェックはありません。コードには既定値の設定、値の上書き、キャッシュもありません。

有効な条件は、環境変数が設定されていることに加えて、chunk が自動選択 (`chunk == 0`) であることです。chunk は引数省略時に 0 で、`--chunk auto` と `--prefill auto` でも 0 になります。正の chunk を明示するとこの診断行は出ません。負数または 4096 超は先にエラーとなります。

## 実行時の詳細

Qwen3.6 エンジンはモデル読み込み後、`chunk == 0` のとき `cudaMemGetInfo` で得た空き VRAM `fr`、各 main layer の routed expert サイズ合計 `experts`、packed Q8_0 copy のサイズ合計 `packed` を使って自動 chunk を決めます。`fr` には `packed` を加えた値を判定・表示に使います。必要量は `experts + 1.1 GiB` と見積もります。`--expert-slots` が指定されていない（値が 0 以下）とき、`--expert-vram` が負なら必要量と空き量を比較し、0 以上なら expert 合計と指定 GiB を比較します。条件を満たせば chunk は 512、そうでなければ 2048 です。

この決定の直後、環境変数が設定されている場合に stderr へ次の形式で出力します。数値は GiB 単位で小数点以下 2 桁です。

```text
strata-q36: chunk rule: free <空き量> GiB (with <packed量> packed), main experts <expert量> GiB
```

その後 `E.init` と `place_experts` に進みます。環境変数は `run()` のこの地点で参照され、関数内の静的キャッシュはありません。通常の実行中に環境変更を再評価するループもありません。`strata` が Qwen3.6 の GGUF を検出すると同じ `run()` に切り替え、独立した `strata-q36` 実行ファイルも同じ関数を呼びます。

このコード経路は CUDA または HIP の GPU backend を有効にしたビルドに含まれます。SYCL 専用ビルドは `STRATA_ENABLE_CUDA` と `STRATA_ENABLE_HIP` を有効にせず、この GPU ターゲット群に入りません。確認した `docs/DETAILS.md` と `docs/AMD_HIP.md` に、この変数を説明する記述はありません。

## 根拠

- 直接参照、出力文字列、出力される条件: `src/qwen35/q36_engine.cu:2439-2441`。
- `chunk` の既定値、`--chunk` / `--prefill` と `auto` の処理、範囲検査、自動判定式、後続処理: `src/qwen35/q36_engine.cu:2346-2368,2412-2447`。
- Qwen3.6 モデルの検出と `run()` への切替: `src/program/generate.cpp:1866-1880`。
- `strata-q36` が同じ `run()` を呼ぶこと、および両ターゲットへのリンク: `src/qwen35/q36_main.cpp:1-5`, `CMakeLists.txt:631-645`。
- GPU ターゲットが CUDA/HIP backend 有効時に作られること: `CMakeLists.txt:304-307`。
