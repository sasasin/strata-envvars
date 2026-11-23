# `HY4S_KVB_HOST`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 版 Hy4-Flash のモデル読込時に、名前に `kv_b_proj` を含む trunk tensor を device slab ではなく pinned host memory に置きます。既定ではこれらの tensor は device 側に置かれます。`embed_tokens` はこの変数に関係なく常に host-resident です。対象 tensor は元の形式のまま読み込まれ、device allocation の対象から外れます（`engine/src/hy4flash/sycl/sy_model.h:50-63,81-85,112-130`）。

## 値と判定

`host_resident` 内の関数ローカル `static const bool` を初期化するとき、`std::getenv` が非 null かつ値の先頭文字が `'1'` かを判定します。文字列全体の比較や数値変換はしません（`engine/src/hy4flash/sycl/sy_model.h:53-57`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| SYCL Hy4-Flash のモデル読込 | `kv_b_proj` は device 側 | 先頭が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `true`, ` 1`, `+1` など先頭が `1` でない値 |

大文字小文字・空白・数値としての妥当性は検査されません。値が `1` で始まるかだけが条件です。対象名に一致する tensor がなければ配置は変わりません。

## 有効になる条件

- `SyModel::load` を通る SYCL Hy4-Flash のモデル読込で評価されます。通常ロードと `--serve` の両経路がこの関数を呼びます（`engine/src/hy4flash/sycl/sy_main.cpp:260-265`; `engine/src/hy4flash/sycl/sy_serve.h:241-247`）。
- manifest 内に名前が `kv_b_proj` を含む trunk tensor が必要です。判定は substring 検索なので、完全一致は要求しません（`engine/src/hy4flash/sycl/sy_model.h:55-56,75-84`）。
- `--info` は別の情報表示経路で `SyModel::load` を呼ばないため、この設定による tensor 配置変更は起きません（`engine/src/hy4flash/sycl/sy_main.cpp:44-67`）。
- この変数を読むコードには CLI 引数や別環境変数による上書き・優先順位分岐はありません。SYCL の選択 device/backend が何であっても `host_resident` 自体に backend 分岐はありません（`engine/src/hy4flash/sycl/sy_model.h:53-57`）。

## 実行時の詳細

関数ローカル `static` は `host_resident` の初回呼び出し時に一度だけ初期化され、以後の呼び出しで同じ判定値を使います。最初の初期化後に環境を変更しても、そのプロセス内では反映されません。モデルロード中、各 manifest tensor の `dsz` を決める時点で判定されます（`engine/src/hy4flash/sycl/sy_model.h:53-57,75-85`）。

有効時は該当 tensor の `dsz` が 0 になり、ロード時に pinned host memory を確保してファイルから直接読み、そのポインタを `ptr` に登録します。無効時は tensor を device slab にコピーして `ptr` に登録します。`kv_b_proj` は `wants_rp` の対象外であり、どちらの配置でも raw tensor として扱われます（`engine/src/hy4flash/sycl/sy_model.h:60-63,81-85,112-130`）。host allocation は `sycl::malloc_host` を使います（`engine/src/hy4flash/sycl/sy_common.h:272-278`）。

## ログと測定値

変数を有効にしたことを個別に表示するログはありません。成功時の既存 `[load] trunk ... -> ... device (+ ... pinned host) ...` 行は、モデル全体の pinned-host byte 合計を出します（`engine/src/hy4flash/sycl/sy_model.h:138-140`）。host memory 確保に失敗すると `halloc: out of host memory (%zu bytes)` を stderr に出して終了コード 3 で終了します（`engine/src/hy4flash/sycl/sy_common.h:272-278`）。tensor の短い読み込みでは `load` が失敗し、通常ロード経路は `load: <error>` を stderr に出して終了コード 1、serve 経路は `ERR cannot load <model>: <error>` をプロトコル出力して終了コード 1 になります（`engine/src/hy4flash/sycl/sy_model.h:112-117`; `engine/src/hy4flash/sycl/sy_main.cpp:260-265`; `engine/src/hy4flash/sycl/sy_serve.h:241-247`）。

この変数を条件にした測定値や実測比較は、調査した Strata ソースからは確認できません。

## 根拠

- `engine/src/hy4flash/sycl/sy_model.h:50-63` — 既定の `embed_tokens` 配置、変数判定、`kv_b_proj` の配置判定、raw tensor の扱い。
- `engine/src/hy4flash/sycl/sy_model.h:75-85,101-140` — tensor ごとの device 容量計算、host/device 読込、ポインタ登録、成功ログ。
- `engine/src/hy4flash/sycl/sy_common.h:262-278` — device allocation と pinned host allocation および失敗時の終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:44-67,260-265`; `engine/src/hy4flash/sycl/sy_serve.h:241-247` — `--info` と通常/serve のロード経路。
