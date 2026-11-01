# `STRATA_Q36_PLACE_DEBUG`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

## 役割

Qwen3.6 専用エンジンの prompt chunk を自動選択する経路で、VRAM の空き容量などの判定材料と、最終的に採用した chunk 数を stderr に表示します。chunk の決定方法や実行動作は変えず、診断ログだけを追加します。

この環境変数を読む実装は `src/qwen35/q36_engine.cu` の1箇所です。`strata-q36` と、GGUF の architecture が `qwen35moe` の場合にこのエンジンへ切り替える `strata` が対象です。Qwen3.6 エンジンはビルド設定で gfx906 を除いて組み込まれます（下記「有効になる条件」）。

## 値と判定

値の内容は parse されません。`std::getenv(...)` が null でないかだけを判定します。

| 環境変数の状態 | ログ |
| --- | --- |
| 未設定 | 出さない |
| 空文字を含む、何らかの値が設定済み | 出す。`0`、`false`、任意の文字列も同じ扱い |

既定値はログなしです。数値変換、境界値検査、無効値時の fallback はありません。設定有無は chunk 自動選択の箇所で都度調べられ、static/local cache はありません。

## 有効になる条件

- prompt chunk が自動選択の場合に限ります。CLI の `--chunk` または `--prefill` の既定値は `auto`（内部値 0）で、このとき VRAM 状況などから chunk を決める経路に入ります。明示的に `--chunk auto` / `--prefill auto` とした場合も同じです。
- `--chunk` / `--prefill` に 0 以外の chunk を指定すると自動選択ブロックを通らず、この環境変数も読まれません。指定 chunk の範囲検査は 0–4096 で行われ、負値はエラーです。
- `STRATA_Q36_CHUNK` が設定されていれば、同じ自動選択ブロック内で `atoi` による変換後、chunk を 256–4096 に clamp します。この override 後の値が `STRATA_Q36_PLACE_DEBUG` のログに出ます。`STRATA_Q36_CHUNK` は非ゼロの CLI chunk を上書きしません（自動選択ブロックに入らないため）。
- ソース上の対象エンジンは Qwen3.6-35B-A3B (`qwen35moe`) 専用です。`strata` はモデルの GGUF architecture を見て専用エンジンへ切り替えます。通常の `strata` 経路でも、同梱の `strata-q36` でも実行されます。
- CMake は gfx906 以外で `strata_qwen35` と `strata-q36` を組み込み、`strata` の Qwen3.6 family switch を有効にします。gfx906 ではこのエンジンがリンクされず、環境変数を読む箇所も実行されません。

## 実行時の詳細

`run()` は引数を解析して範囲を検査し、モデルをロードした後に chunk を決めます。chunk が自動選択の場合、空き VRAM、routed experts の必要量、packed Q8 コピーなどを使って初期値を決め、設定済みなら `STRATA_Q36_CHUNK` の override を適用します。その後、この変数が設定済みなら次の形式で stderr に一行を出します（数値は実行時の値です）。

```text
strata-q36: chunk rule: free %.2f GiB (raw %.2f, with %.2f packed), main experts %.2f GiB, chunk %d
```

このログは `E.init()` および expert 配置処理より前に出ます。値が未設定、または CLI で非ゼロ chunk を指定した場合は、この診断行は出ません。ログ表示による失敗・終了経路はありません。変数が chunk 値や expert 配置、prompt/decode 計算を直接変更する処理は確認できません。

## 根拠

- 候補名の全参照と設定有無判定、自動選択・`STRATA_Q36_CHUNK` override・診断行: `src/qwen35/q36_engine.cu:3848-3852`。
- CLI の `--chunk` / `--prefill` と `auto` の変換、既定 chunk、範囲検査、モデルロード順: `src/qwen35/q36_engine.cu:3725-3728,3747,3787-3805`。
- 初期 chunk 選択の VRAM/experts 条件: `src/qwen35/q36_engine.cu:3809-3847`。
- 診断行の後に engine init と expert 配置を行う順序: `src/qwen35/q36_engine.cu:3853-3856`。
- `strata` の `qwen35moe` family switch: `src/program/generate.cpp:2980-2995`。
- gfx906 を除くエンジンのビルドと `strata-q36` executable の定義: `CMakeLists.txt:885-904`。
- Qwen3.6 専用エンジンが NVIDIA / AMD 向けで Intel Arc / Mac 向けではないという製品資料: `docs/QWEN36.md:7-9`。これは環境変数の動作判定ではなく、コード上のログ処理の根拠は `src/qwen35/q36_engine.cu` によります。
