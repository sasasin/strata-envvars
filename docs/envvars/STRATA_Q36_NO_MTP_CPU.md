# `STRATA_Q36_NO_MTP_CPU`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数を設定すると、Qwen3.6 CUDA エンジンが自動選択する「主層の routed experts はすべて VRAM、MTP 層の experts だけ CPU pool に置く」配置 (`mtp_only`) を抑止します。必要な場合は通常の hybrid 配置になり、CPU pool は MTP 層だけでなく全層の routed experts を扱います。変数名に `=1` と書いた説明コメントがありますが、実装は値を読まず設定有無だけを判定します（`engine/src/qwen35/q36_engine.cu:4273-4307,4344-4350`）。

Strata の `--model` / `--native` で GGUF の architecture が `qwen35moe` の場合に Qwen3.6 エンジンへ切り替わり、単体 `strata-q36` も同じ `run()` を使います（`engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Qwen3.6 `place_experts()` | MTP 専用 CPU 配置の条件判定を通せる | 値は問わず、存在すれば専用配置を抑止。空文字、`0`、`1`、`true`、任意文字列すべて同じ | なし（値の変換・検証をしない） |

実装は `std::getenv(...) == nullptr` の比較です。したがって未設定だけが「許可」、空文字を含む設定済みの値はすべて「禁止」です。数値変換、前後空白の処理、大文字小文字の比較はありません。設定値の既定値は配置処理に入った時点では unset 相当です（`engine/src/qwen35/q36_engine.cu:4276-4279,4300-4307`）。

## 有効になる条件

- 値が未設定で、GGUF のメタデータに MTP ブロックがあり、全層の experts 合計が VRAM 予算を超えている必要があります。MTP の有無は `m.has_mtp`（`g.n_mtp_layers > 0`）で決まり、`--mtp 0` でも MTP ブロックと experts はロード・配置の対象に含まれます（`engine/src/qwen35/q36_engine.cu:1455-1461,1518-1524`）。
- MTP 専用配置は `--expert-slots` が未指定相当（`slots <= 0`）かつ `--expert-vram` が未指定相当（`vram_gib < 0`）の自動配置でのみ試されます。これらを指定した場合は当該配置分岐を通りません（`engine/src/qwen35/q36_engine.cu:4301-4316`）。
- 主層の experts と追加 64 MiB が現在の予算に収まる場合に `mtp_only` が立ちます。収まらない場合、通常の全層 hybrid 配置へ進みます（`engine/src/qwen35/q36_engine.cu:4302-4316`）。
- MTP 専用配置にせず、なお全層 experts が予算と実空き容量に収まる場合は、通常の「全 experts を VRAM に置く」分岐が先に成功します。この変数は全 VRAM 配置を抑止しません（`engine/src/qwen35/q36_engine.cu:4318-4335`）。
- `STRATA_Q36_KEEP_PACKED` が設定されていると、先行する packed Q8_0 コピー解放が抑止され、その解放を前提とした予算判定にも影響します。`STRATA_Q36_NO_MTP_CPU` はその解放判定にも使われ、設定時は MTP 専用配置を見込んだ主層予算の条件を使いません（`engine/src/qwen35/q36_engine.cu:4271-4292`）。
- CPU expert pool を含まない build では hybrid 配置が使えず、全 experts が VRAM に収まらない場合は失敗します。該当時のエラーは `the routed experts (...) do not fit in VRAM, and this build has no CPU expert pool (STRATA_NATIVE_EXPERTS=OFF)` です（`engine/src/qwen35/q36_engine.cu:4337-4342`）。

## 実行時の詳細

変数はモデルロードと `Engine::init()` の後、`place_experts()` が VRAM 状況を測って配置を決める際に読みます（呼び出し: `engine/src/qwen35/q36_engine.cu:5522-5527`）。関数内で2回 `getenv` します。1回目は packed Q8_0 コピー解放の見積もり条件、2回目は MTP 専用配置を試す条件です。static cache はなく、この配置処理後に環境を変更しても、既に決まった `mtp_only` や配置は変わりません（`engine/src/qwen35/q36_engine.cu:4276-4307`）。

未設定で専用配置が選ばれた場合、全主層の experts を GPU メモリへコピーし、MTP 層は CPU 側 host arena に保持して GPU slot と CPU pool を使う構成になります。主層がすべて VRAM にあるため、decode graph は維持されます（`engine/src/qwen35/q36_engine.cu:4344-4349,4397-4446`）。この変数を設定して `mtp_only` が偽なら `E.main_hybrid` が真になり、主層も含めて hybrid 配置され、host 側に全層分の experts を確保します（`engine/src/qwen35/q36_engine.cu:4344-4350,4397-4446`）。

通常の hybrid 配置が VRAM に収まらない場合、`place_experts()` は `false` を返し、呼び出し元が理由を stderr に出して終了コード 1 で終了します（`engine/src/qwen35/q36_engine.cu:4380-4385,5523-5526`）。

## ログと測定値

専用配置が成立した場合は stderr に `strata-q36: every main layer's routed experts in VRAM (... GiB); the MTP block's: ... in VRAM, the rest on the CPU pool (its drafts only)` と出ます。通常の hybrid 配置では `strata-q36: hybrid experts: ... per layer in VRAM ... all ... host memory ...` の行が出ます（`engine/src/qwen35/q36_engine.cu:4530-4539`）。この変数自体の値を表示するログはありません。

`docs/DETAILS.md` は Qwen3.6 エンジンが独自の `--pool-workers` と既定配置を持つことを記載していますが、この変数の動作や比較測定値は記載していません（`docs/DETAILS.md:1425-1431`）。本調査では性能値を追加していません。

## 根拠

- `engine/src/qwen35/q36_engine.cu:4247-4316` — 全 experts の計上、環境変数の2つの有無判定、MTP 専用配置の条件。
- `engine/src/qwen35/q36_engine.cu:4318-4350,4397-4446,4530-4539` — 全 VRAM 配置 / hybrid 配置とログ。
- `engine/src/qwen35/q36_engine.cu:1455-1461,1518-1524` — `--mtp` と独立した MTP ブロックのロード。
- `engine/src/qwen35/q36_engine.cu:5522-5527` — 配置処理の呼び出しと失敗時の終了。
- `engine/src/program/generate.cpp:3804-3818`、`engine/src/qwen35/q36_main.cpp:1-5` — Qwen3.6 エンジンへの入口。
