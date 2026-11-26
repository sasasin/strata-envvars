# `STRATA_Q36_KEEP_PACKED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Qwen3.6 engine が routed expert の配置を決めるとき、条件を満たした場合に GPU 上の packed Q8_0 decode コピーを解放して全 expert を VRAM に置く最適化を抑止する。設定すると packed コピーを保持し、通常の slot + CPU pool を使う hybrid 配置へ進むためのフラグである。ただし、設定だけで必ず全層の hybrid 配置になるわけではなく、後続の配置判定が優先される。読み取りと解放処理は `place_experts` にある（`engine/src/qwen35/q36_engine.cu:4247-4289`）。

この環境変数自体は値を数値化・真偽値 parse せず、存在確認に使う。コピー解放条件に入らなければ配置への影響はない（`engine/src/qwen35/q36_engine.cu:4271-4279`）。

## 値と判定

`std::getenv(...) == nullptr` かどうかだけを判定する。未設定なら解放最適化を許可し、何らかの値が設定されていれば最適化を抑止する。空文字列も「設定あり」と判定される。`1`、`0`、`true`、`false`、`0anything`、大文字小文字、前後の空白はいずれも文字列内容を検査されず、設定されていれば同じ扱いである。数値変換・値域・無効値 fallback はない（`engine/src/qwen35/q36_engine.cu:4277-4279`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `place_experts` のコピー解放判定 | 後述の配置条件を満たせばコピーを解放 | 空文字、`1`、`0`、`true`、`false`、任意の文字列。すべて解放判定を抑止 | なし。値の内容による無効値判定はない |

## 有効になる条件

環境変数が設定されていても、次の条件がすべて成立する場合に限って解放を抑止する効果がある。条件式は `place_experts` にある（`engine/src/qwen35/q36_engine.cu:4262-4279`）。

- `--expert-slots` が 0 以下である。正の slot 数を強制した場合はコピー解放判定に入らない（CLI 値の読み取り: `engine/src/qwen35/q36_engine.cu:5384-5386`）。
- `--expert-vram` が未指定相当の負値である。既定値は `-1.0`。0 以上の明示値ではこの判定に入らない（`engine/src/qwen35/q36_engine.cu:5343-5345,5384`）。
- 初期の VRAM 空き容量から 768 MiB の reserve を引いた予算より、expert と MTP block を含む必要量 `total` が大きい。
- model load 時に登録された packed Q8_0 コピーの合計 `packed_bytes` が 0 より大きい。登録対象は type 8 の tensor のうち `native_q8_0_packed_enabled()` と `native_q8_0_packed_eligible(...)` を満たすもの（`engine/src/qwen35/q36_engine.cu:1439-1449`）。
- コピーを返せば収まる見込みがある。具体的には `total <= budget + packed_bytes`、または MTP block の CPU 配置が許され、`main_need <= budget + packed_bytes + slack`。後者の `mtp_cpu_ok` は `STRATA_Q36_NO_MTP_CPU` が未設定のときだけ真（`engine/src/qwen35/q36_engine.cu:4275-4279`）。

この条件外では変数の有無にかかわらずコピー解放分岐は実行されない。例えば既に全 expert が予算内に収まる場合、packed コピーがない場合、slot 数や expert VRAM 予算を CLI で指定した場合はこの変数は配置を変えない。

## 実行時の詳細

Qwen3.6 model のロードと `Engine::init` の後、expert の配置を始めるときに `place_experts` がこの変数を読み取る。読み取りは関数内の直接呼び出しで、static cache やリクエストごとの再評価はない。main 経路では `place_experts` は一度呼び出されるため、判定後のプロセス環境変更ではその配置結果は変わらない（呼び出し位置: `engine/src/qwen35/q36_engine.cu:5522-5524`）。

変数が未設定で解放条件を満たすと、Strata は device synchronize の後、各 packed コピーを `native_q8_0_packed_unregister` で登録解除し、`cudaFree` し、`m.packed` を空にして graph を reset する。その後に空き VRAM を再取得し、更新された空き容量で配置を続ける（`engine/src/qwen35/q36_engine.cu:4280-4292`）。設定時はこのまとまりを飛ばし、packed コピーを保持したまま通常の配置判定へ進む。

後続の判定では、全 expert が予算内なら全 expert を VRAM に配置する経路も残る（`engine/src/qwen35/q36_engine.cu:4318-4335`）。収まらなければ、`STRATA_Q36_CPU_POOL` が有効な build では hybrid 配置を計画し、main layer の CPU pool 参加、slot 数、prompt streaming / staging の可否を決める。MTP だけを CPU pool に置く経路もあり、`STRATA_Q36_NO_MTP_CPU` が設定されるとその経路は選ばれない（`engine/src/qwen35/q36_engine.cu:4301-4316,4343-4376`）。この変数は CLI の優先順位を上書きせず、上記の `--expert-slots` / `--expert-vram` 条件が成立しない場合には何もしない。

## ログと測定値

未設定でコピーを解放したとき、stderr に次のログが出る。コピーサイズは実際に合計した値である（`engine/src/qwen35/q36_engine.cu:4287-4290`）。

```text
strata-q36: the packed Q8_0 decode copies (%.2f GiB) given back so that every routed expert fits in VRAM (STRATA_Q36_KEEP_PACKED=1 keeps them and runs the hybrid mode)
```

このログは環境変数が設定されて分岐を抑止した場合には出ない。後続の hybrid 計画が VRAM に収まらなければ、例えば `not enough VRAM left for the hybrid experts' buffers and slots (...)` をエラー文字列として返し、呼び出し元が `strata-q36: ...` と stderr に出して終了コード 1 で終了する。CPU expert pool のない build では、expert が VRAM に収まらない場合に `the routed experts (...) do not fit in VRAM, and this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)` を出して同じく配置失敗となる（`engine/src/qwen35/q36_engine.cu:4337-4342,4380-4385,5523-5526`）。

Strata のソースコメントはコピー解放後の decode を「bitwise the same outputs, a little slower」と説明しているが、ここでは測定値を示すものではない（`engine/src/qwen35/q36_engine.cu:4267-4270`）。

## 根拠

- `engine/src/qwen35/q36_engine.cu:1439-1449` — packed Q8_0 コピーの作成・登録条件。
- `engine/src/qwen35/q36_engine.cu:4247-4292` — 配置予算、対象環境変数の読み取り、packed コピー解放とログ。
- `engine/src/qwen35/q36_engine.cu:4301-4349` — MTP only / 全 VRAM / CPU pool hybrid の後続経路と build 条件。
- `engine/src/qwen35/q36_engine.cu:5343-5386,5522-5526` — CLI 既定値、引数、配置呼び出しと失敗終了。
- `engine/cmake/strata_gpu_engine.cmake:565-583` — Qwen3.6 engine の build 登録、gfx906 除外、`STRATA_NATIVE_EXPERTS` による CPU pool macro。
