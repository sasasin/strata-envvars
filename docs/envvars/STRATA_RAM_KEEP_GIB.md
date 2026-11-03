# `STRATA_RAM_KEEP_GIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

`strata generate` の expert RAM 配置で、expert arena を確保した後に空けておく RAM を GiB 単位で指定します。値が正なら、arena の必要量にこの値を加えて空き RAM と比較します。arena に収まらず、RAM-copy fallback が選ばれる場合は、RAM copy の安全 headroom を少なくともこの値にします。ただし `STRATA_RESIDENT_HEADROOM_GIB` が有効値なら、その値が fallback headroom を決めます。

この変数は `--ram-keep-gib W` と同じ設定です。CLI フラグを一度でも指定した場合は環境変数を読みません。既定値は 0 GiB です。

## 値と判定

実装は `std::getenv` で値を取得し、未設定・空文字を除外したうえで `std::atof(v) > 0.0` を判定します。文字列全体の妥当性確認はなく、`atof` が先頭から数値に変換できた部分を使います。

| 環境値 | 結果 |
|---|---|
| 未設定、空文字 | 0 GiB（既定値） |
| `0`、負値、数値に変換できない文字列 | 0 GiB。警告なし |
| 正の有限値 | GiB をバイト数へ変換。小数バイトは整数変換で切り捨て |
| `2junk` のように数値の後ろに文字がある値 | `atof` が読める先頭の数値部分（この例なら 2 GiB）を使用 |
| 正の無限大など 1024 以上 | `ram_keep_from_gib` が最大 1024 GiB に制限 |
| `nan` | `> 0.0` が偽になるため 0 GiB |

CLI の `--ram-keep-gib` は別の判定です。`atof` の結果が 0 以上なら受理し、環境変数より優先します（`abc` は `atof` で 0 となり受理される一方、負値や NaN は stderr に `strata generate: --ram-keep-gib needs N >= 0` を出して終了コード 2）。CLI フラグを複数回指定した場合は最後の値が残ります。

根拠: `src/program/generate.cpp:3292-3297,3657-3662,3692-3697`; `include/strata/core/ple_residency.hpp:82-89`。

## 有効になる条件

- 通常の `strata generate` オプション解析経路で読み取られます。Qwen3.5 MoE は `STRATA_HAVE_QWEN35` が有効なビルドで専用 runner に早期 dispatch されるため、この `generate.cpp` 側の読み取り経路を通りません（`src/program/generate.cpp:3269-3284`）。
- 値は RAM 設定の解析時に `Options` へ取り込まれます。選択した環境値を後から変えても、その実行中の `o.ram_keep` は再評価されません。プロセスを起動し直せば新しい値が読まれます。
- 効果が現れるのは expert arena を開く経路です。arena の RAM 判定には arena と spare blob の必要量に `ram_keep` を加えます。共有 expert arena ファイルを使う場合はホスト RAM 判定をスキップするコード経路があります。
- arena が RAM 不足で開けず fallback が許可された場合、通常は `--mmap-experts` 相当へ移ります。静的 expert profile があり、`STRATA_ARENA_FALLBACK_RESIDENT` の先頭文字が `0` でなければ、利用可能 RAM から headroom を引いた予算で hottest experts を RAM copy にし、残りはファイルから読みます。条件を満たさなければ fallback は通常のファイル読み取りです。
- fallback の headroom は Windows で既定 8 GiB、その他で 4 GiB です。正の `ram_keep` があれば `max(ram_keep, safety headroom)` になります。`STRATA_RESIDENT_HEADROOM_GIB` が設定され、`atof` の結果が 0 以上なら、それが headroom を置き換えます。空文字や数値変換できない文字列も `atof` では 0 になるため、この変数が設定されている場合は headroom が 0 になり得ます。明示値を 0 にすると安全 headroom より小さくできます。
- `--resident-budget-gib` / `--resident-experts` のような明示 RAM mode でも、`ram_keep` は arena 判定と headroom の計算に使われます。明示的な `STRATA_RESIDENT_HEADROOM_GIB` はその headroom を優先します。

根拠: `src/program/generate.cpp:3692-3700,7072-7088,7306-7317,7321-7343`; `src/core/expert_source.cpp:5873-5884`; `include/strata/core/ple_residency.hpp:74-81,91-116`。

## 実行時の詳細

環境変数は generate の CLI 引数解析後に一度読み取られます。`--ram-keep-gib` がなければ、設定値が存在し、空でなく、`atof` の結果が正のときに `ram_keep_from_gib` へ渡します。その後 `STRATA_RESIDENT_HEADROOM_GIB` を評価し、明示 headroom がない場合は `resident_headroom` を `ram_keep` 以上に引き上げます。arena source には `ram_keep_bytes` と fallback headroom が渡されます。

arena は、必要量（arena と spare blob）に keep 値を足した量が現在の空き RAM 以下の場合に選ばれます。さらに fallback が許可されている場合、hard memory limit（例: cgroup limit）との比較にも keep 値と headroom が反映されます。空き RAM が足りない場合は既定で最大 20 秒待ち、待機状況を stderr に出します（`STRATA_ARENA_RAM_WAIT_S` が待機秒数を変えます）。待機後も不足し fallback が許可されていれば arena open が RAM-short を返し、generate は不足量を含む警告行を出して mmap 経路へ進みます。fallback が禁止されていて hard limit が足りない場合は arena open が失敗し、generate は stderr に `strata generate: <詳細>` を出して終了コード 1 になります。fallback も hard limit refusal もない空き RAM 不足は警告を記録したうえで arena の読み込みを続けます。

`ram_keep > 0` の場合は起動時に stderr へ、arena を使う条件と fallback 時に残す headroom を示す `strata generate: --ram-keep-gib ...` 行が出ます。値が 0、未設定、空、無効文字列だけの場合、この行は出ません。設定値の parse 失敗に対する専用警告はありません。

根拠: `src/program/generate.cpp:3692-3700,7072-7088,7306-7315,7321-7347`; `src/core/expert_source.cpp:5866-5905,5907-5967`; `include/strata/core/ple_residency.hpp:93-116`。

## アプリからの設定

同梱アプリの `apps/host/server/native-resources.mjs` は `profile === 'work'`、RAM と expert arena のサイズが正で、`--resident-experts` / `--mmap-experts` / `--resident-budget-gib` / `--ram-keep-gib` の明示指定がない場合に、この設定を実行環境へ加えます。対象 engine が `0.1.56` 以上と判定され、ユーザー自身の truthy な `STRATA_RAM_KEEP_GIB` がなければ、PC RAM の 20% を切り上げて 5〜8 GiB に clamp した値を設定します。アプリ自身の環境値がある場合は保ちます。engine version が古い、または判定不能ならこの変数を渡さず、別の legacy 設定経路を使います。`strata serve` と full-performance profile ではアプリは自動設定しません。

根拠: `apps/host/server/native-resources.mjs:79-107,109-117`。これはアプリ側の設定であり、エンジンの `std::atof` 判定とは別です。

## 参照資料

`docs/DETAILS.md:749-764` は、arena 不足時の RAM-copy fallback、keep 値、Windows / その他の安全 headroom、アプリの「Leave 20% for my work」からの設定を説明しています。上記の値判定と優先順位は調査対象 commit の実装に基づきます。
