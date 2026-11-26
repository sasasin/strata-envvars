# `STRATA_PIN_BY_NEED_SKIP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

## 役割

`STRATA_PIN_BY_NEED` による expert arena の pin-by-need が動くとき、GPU キャッシュに入ると見積もる profile 上位件数 `skip`（R）を指定する。`skip` 件は GPU-resident として pin の優先順位を下げ、残りの ranked pair と profile にない pair が先に pin 対象になる。値を変えても profile の順位や GPU キャッシュ容量そのものは変更しない。`ArenaExpertSource::set_pin_priority()` に渡す順位列と、その後 `open()` が登録する arena の範囲選択を変える（`engine/src/program/generate.cpp:8771-8774,8793-8844`; `engine/include/strata/core/expert_source.hpp:1363-1373`）。

## 値と判定

pin-by-need が有効で、かつ profile があり、単一 GPU で helper cache がないときだけ、この変数を読み取る。未設定または空文字列なら、値を parse せず `--expert-cache` または GPU 空き容量から `skip` を自動計算する。非空文字列なら `std::atoll` で整数変換し、負値を 0 にし、さらに profile 件数を上限として `skip` にする。`atoll` の後ろにある文字列は検査されないため、先頭の整数部分が使われる（`engine/src/program/generate.cpp:8793-8827`）。

| 入力 | 判定と結果 |
|---|---|
| 未設定 | 自動計算。`--expert-cache N` が正なら N slots 相当の byte 数、それ以外は GPU 空き容量から予約分を引いた byte 数を基にする。 |
| 空文字列 | 未設定と同じ自動計算。 |
| `0`、`-1`、整数に変換できない文字列（例: `abc`） | `atoll` と負値の下限処理により 0 件。全 ranked pair が「GPU-resident と見積もる件数」の外になる。 |
| 正の整数（例: `1`、`25`） | 指定件数。ただし profile 件数までに制限する。 |
| profile 件数以上の整数 | profile 件数に制限する。 |
| 整数に続く文字列（例: `3tail`、`0anything`） | `atoll` が読む先頭の整数部分を使う（それぞれ 3、0）。文字列全体の妥当性は検査しない。 |
| 先頭空白と整数（例: ` 2`）、符号（例: `+2`） | `atoll` の変換規則に従い 2 件。Strata 側では trim や符号の個別処理をしない。 |
| `true`、`false` | 数値接頭辞がないため 0 件。真偽値文字列としては扱わない。 |

文字列全体との比較、大文字小文字判定、Strata 側での trim、変換エラー検査は行わない。`atoll` に数値接頭辞がない非空文字列は 0 になる。整数型で表現できない極端な入力については、Strata 側で範囲エラーを検査していない（`engine/src/program/generate.cpp:8795-8796`）。

## 有効になる条件

- arena 読み込み経路であること。`--mmap-experts` の file source 経路ではこの読み取りに到達しない（`engine/src/program/generate.cpp:8621-8629,8747-8754`）。
- pin-by-need が有効であること。`STRATA_PIN_BY_NEED` が未設定・空でなく、先頭文字が `'0'` 以外の場合、または後述の Windows HIP 既定条件を満たす場合に有効になる。`1`、`true`、`2` は有効で、`0`、`0anything` は無効。空白で始まる値も、その空白が先頭文字なので有効（`engine/src/program/generate.cpp:8774-8784`）。
- `--expert-profile` で読み込んだ profile に ranked pair があること。profile 読み込み失敗時は `strata generate: <error>` を stderr に出して終了コード 1 で戻る（`engine/src/program/generate.cpp:6746-6751`）。profile が空なら pin-by-need の無効理由 `it needs --expert-profile (the ranking)` が出る（`engine/src/program/generate.cpp:8784-8791`）。
- 単一 GPU で、`--peer-device` が指定されず、他 GPU の helper cache がないこと。layer split / peer GPU の場合は `not with a layer split or a peer GPU`、helper cache がある場合は `not with helper caches on other GPUs` と stderr に出し、prefix pinning を維持する。これらの場合、skip の値は読み取られない（`engine/src/program/generate.cpp:8785-8796`）。
- Windows HIP build では、`STRATA_PIN_BY_NEED` が未設定または空の場合に限り、WDDM 下の discrete GPU、profile あり、単一 GPU、peer device なし、helper cache なし、かつ `strata::qwen_defaults_026()` が false のとき pin-by-need が既定で有効になる。その他の build ではこの既定有効分岐はコンパイルされず、`STRATA_PIN_BY_NEED` による明示的な有効化が必要（`engine/src/program/generate.cpp:8775-8784`）。
- `STRATA_PIN_BY_NEED_SKIP` 自体に CLI 引数や別環境変数による上書きはない。値が空・未設定のときだけ `--expert-cache` が自動算定に使われる（`engine/src/program/generate.cpp:8795-8827`）。

## 実行時の詳細

profile は arena の設定より前に読み込まれる。pin-by-need が有効な分岐内で `STRATA_PIN_BY_NEED_SKIP` を一度読み、明示値がなければ、正の `--expert-cache` を使うか、GPU の空き byte 数から VRAM reserve、prefill、draft head、pipeline 分を差し引く。後者は計算した容量を 98% にして、profile の順位順に各 pair の slot/blob byte 数を加算し、容量に収まる件数を `skip` とする（`engine/src/program/generate.cpp:6746-6789,8793-8827`）。

profile の `skip` 件を GPU-resident 側として列の末尾へ置き、それ以外の ranked pair を先に、次に profile にない pair を layer 順に置く。`skip` が 0 なら ranked pair 全件が先行側となり、`skip` が profile 件数なら profile 全件が後順位側となる。実際に pin される範囲数・byte 数は `ArenaExpertSource::open()` の結果で決まり、この変数だけでは pin 成功量を保証しない（`engine/src/program/generate.cpp:8829-8844,8871-8875,8917-8932`; `engine/include/strata/core/expert_source.hpp:1363-1373`）。

読み取りは `generate` の起動処理中、arena を開く前に行われ、関数内 static cache ではない。プロセス起動後に環境値を変えても、その起動中の計算には反映されない。サーバーか通常 CLI かによる別の読み取り箇所はなく、子プロセスへの転送もこのコードにはない（`engine/src/program/generate.cpp:8793-8844`）。

## ログと測定値

有効な分岐では stderr に `strata generate: pin by need: %zu of the %zu ranked pairs taken as GPU-resident (STRATA_PIN_BY_NEED_SKIP=<n> sets it), %zu candidates to pin` を出し、arena を開いた後、候補から実際に pin できた量を `strata generate: pin by need: %zu ranges, %.2f GiB pinned, %.1f %% of the non-resident experts (%lld of %lld layers have a PCIe share)` と報告する（`engine/src/program/generate.cpp:8841-8844,8917-8932`）。skip の値が無効化条件により読まれない場合は、その理由を示す `pin by need: off (...)` が stderr に出る。既定の prefix pinning のままなら上記 pin-by-need 件数ログは出ない。

この変数で `skip` を指定した場合の測定値は、調査対象のソースと `docs/DETAILS.md` に記載されていない。`docs/DETAILS.md` は `STRATA_PIN_BY_NEED` 自体の説明を含むが、skip の調整値に関する測定ではない（`docs/DETAILS.md:293-295`）。

## 根拠

- 直接の環境読み取りと変換、自動算定、候補順位の組み立て、ログ: `engine/src/program/generate.cpp:8771-8845`
- profile の読み込みと失敗経路: `engine/src/program/generate.cpp:6746-6751`
- mmap / arena 分岐と arena open 後の結果: `engine/src/program/generate.cpp:8621-8629,8747-8754,8871-8875,8917-8932`
- pin 優先順位の受け渡し: `engine/include/strata/core/expert_source.hpp:1363-1373`
- pin-by-need の概要との照合: `docs/DETAILS.md:293-295`
