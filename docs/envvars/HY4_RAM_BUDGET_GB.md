# `HY4_RAM_BUDGET_GB`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4 GPU runner の tiered expert loading で、CPU mode 時に host RAM に保持する expert の上限を GB 単位で指定する。値は自動 RAM 予算の代わりに使われ、必要なら host experts の cold tail をモデルファイルからオンデマンドで読む SSD tier に回す。また CPU mode がまだ選ばれていない場合、GPU に載らない host experts の見積もりがこの予算を超えると CPU mode を自動で有効にする。読み取りと適用は `load_experts_tiered` 内で行われる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:792-805,810-834,842-849`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `load_experts_tiered` の全呼び出し | `STRATA_HY4_RAM_GB` が設定されていればその値を使用。どちらも未設定なら OS の RAM 上限・利用可能量、Vision の有無、`HY4_HOST_NEED_GB`、`HY4_ENGRAM_CACHE_MIB` から自動計算 | `atof` が数値として変換できる非負値。例: `0`, `1`, `12.5`, `1GB`（数値接頭辞 `1` として変換）。空白や数値の後ろの文字列は全体検証されず、`atof` の変換規則に従う | 空文字や数値で始まらない文字列は `atof` により `0` となる。負値も `std::max(0.0, atof(...))` で `0` に丸められる。例: `-1`, `abc`, 空文字は予算 0。厳密な文字列形式・小数桁・有限上限の検証はない |

環境変数の存在判定は `getenv(...)` の非 null 判定なので、空文字も「設定済み」として扱われます。その場合は fallback せず `atof("") == 0` 相当の予算になります。対象変数が存在すれば、値が空または無効でも `STRATA_HY4_RAM_GB` は参照されません（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:810-812`）。

CLI との関係:

- `--ram-experts-gb N` は引数を `atof` で読み、N が `>= 0` のとき `STRATA_HY4_RAM_GB` を設定する。直接読む `HY4_RAM_BUDGET_GB` は設定しないため、起動時から対象変数が存在するとそちらが優先される。ただし CLI 値は `g.ram_experts_gb_cap` にも入り、予算をその値以下に clamp するので、CLI 値は上限として残る（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-458,654-655`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:830-832`）。
- `--ram-experts-gb` の負値は環境変数を設定せず、RAM cap も無効（初期値と同じ負値）になる。したがって既存の `HY4_RAM_BUDGET_GB` があればその値が使われる（同上）。
- `--ssd-experts` は `HY4_RAM_BUDGET_GB=0` と `STRATA_HY4_RAM_GB=0` を上書き設定し、RAM cap も 0 にする。引数処理は左から順なので、その後ろに `--ram-experts-gb N` を置いても対象変数の 0 が優先し、CLI cap が追加上限になる。`--ssd-experts` が後なら対象変数・別名とも 0 に設定される（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,455-465`）。

## 有効になる条件

- Hy4 GPU model の expert loading が `with_experts` 経路に入り、full expert load が選べず `load_experts_tiered` を呼ぶこと。full load が成立した場合、この予算は読み取られない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1425,1434-1503`）。
- 予算によって RAM 常駐 expert 数や SSD cold tier が決まるのは `cpu_mode` の場合。`HY4_CPU_EXPERTS`（`atoi != 0`）または host/GPU 比率や CPU 能力による既定判定で CPU mode が選ばれる。CPU mode が false でも、host expert 見積もりが予算を超える場合はこの関数内で自動的に true になり、理由ログを出す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-849,1487-1499`）。
- CLI の `--ram-experts-gb` が非負なら、その値は環境変数由来の予算をさらに上から制限する。`--ssd-experts` は予算と cap をともに 0 にする（`engine/src/hy4flash/run/hy4_main.hip.cpp:455-465`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:830-832`）。
- 直接の読み取りは `hy4_gpu_model.hip.h` の Hy4 CUDA/HIP 共通 runner 実装にあり、Python server 固有の読み取りはない。サーバーモードでも同じ model load 経路に到達した場合に適用される。モデル形式、GPU 配置などの他の条件が満たされず tiered load 自体に進まない場合は作用しない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:792,1420-1503`; `engine/src/hy4flash/run/hy4_main.hip.cpp:397-398,658-665`）。

## 実行時の詳細

`load_experts_tiered` の開始時に RAM 上限・利用可能量を取得し、まず `HY4_RAM_BUDGET_GB`、次に互換名 `STRATA_HY4_RAM_GB` を調べる。どちらもなければ Windows とそれ以外で異なる OS reserve を使い、Vision の追加分、`HY4_HOST_NEED_GB`、`HY4_ENGRAM_CACHE_MIB` を考慮した自動予算を計算する。CLI RAM cap が非負ならその後に最小値を取る（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:804-834`）。

予算は `gib_to_bytes` で byte 数に変換される。host experts の見積もりが上回り CPU mode がまだ false なら、4-tier CPU + SSD cold-expert streaming に切り替える。CPU mode 中に host resident expert の合計が予算を超える場合は rank の低い方から予算内に収め、以降の coldest ranks を tier 3（SSD）にする。値は model load 中に評価され、static cache はなく、fallback の pinned-host allocation 失敗で再帰的に同じ loader が呼ばれた場合も再読込する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-849,1090-1110,1157-1172`）。

予算は GPU VRAM の予算そのものではなく、expert の配置先選択・生成 token の値を直接変更する設定でもない。CPU/SSD tier に配置された expert の読込経路が変わる（同ファイル `:1084-1110,1227-1248`）。

## ログと測定値

- 自動 CPU mode 切替時、stderr に `[load] host experts %.1f GB exceed safe RAM budget %.1f GB (avail %.1f / %.1f GiB); auto-enabling 4-tier CPU + SSD cold-expert streaming` を出す（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:845-849`）。
- CPU mode で host experts が予算を超える場合、stderr に `[load] RAM budget %.1f GB for the host experts (%.1f GB wanted): %llu experts (%.2f GB, the coldest ranks) stay on the SSD` を出す（同ファイル `:1097-1110`）。超過しない場合、この RAM budget の cold-tail ログは出ない。
- tiered load 完了時は配置数と RAM/SSD 容量を `[load] experts 4-tier: ...` または multi-GPU のログに出す（同ファイル `:1251-1262`）。expert read failure は `err = "expert read failed"` となり、呼び出し元が `experts: %s` を stderr に出して load を失敗させる（同ファイル `:1224-1226,1499-1501`）。この環境変数に固有の追加ログや測定値は確認できなかった。

## 根拠

- 読み取り、優先順位、自動予算、CLI cap: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:804-834`
- 予算超過時の CPU mode 切替とログ: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:842-849`
- RAM resident / SSD cold tier とログ: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1090-1110,1224-1228,1251-1262`
- tiered loader の条件と CPU mode 選択: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1420-1503`
- CLI による環境変数設定・上書き: `engine/src/hy4flash/run/hy4_main.hip.cpp:455-465,654-659`
- 環境変数 setter の上書き動作: `engine/src/hy4flash/run/hy4_gpu_model.hip.h:405-410`
