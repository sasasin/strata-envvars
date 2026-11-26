# `STRATA_PEER_HOT_AT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--peer-device` と `--expert-profile` を使うとき、ランキングの先頭から何件を `STRATA_PEER_HOT` による peer 分配の対象にするかを指定します。対象内の一部をランキング後方へ移し、primary cache がその前後の項目を取った後、peer cache が primary にない項目を順位順に選べるようにします。環境変数自体は cache 容量や分配率を指定しません。CUDA/HIP 実装と SYCL 実装の双方で値を読みますが、SYCL の peer tier は未実装のため実際の cache 分配には至りません。`engine/src/program/generate.cpp:6757-6785`、`engine/sycl/src/program/generate.cpp:3791-3819`、`engine/src/core/peer_experts.cpp:264-280`、`engine/sycl/src/core/peer_experts.cpp:19-22`

## 値と判定

`std::getenv` が返す文字列を `std::atoll` で符号付き十進数として変換し、その結果を `size_t` に変換した後、プロファイルの項目数との小さい方を使います。文字列全体の検査や範囲エラーの検査はありません。`atoll` は先頭の空白と符号を許し、数字の後ろに非数字があっても数字部分を使います。数字に変換できない文字列と空文字は 0 になります。大文字小文字は数値変換に関係しません。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP または SYCL、かつ `--peer-device >= 1` と `--expert-profile` 指定あり | 既定値 8700。プロファイル長を超える場合は全項目数に切り詰め | 正の数値部分を持つ文字列。例: `1`、`8700`、`  +12tail`。値はプロファイル長を上限とする | 空文字、`0`、`0anything`、`true`、`abc` は 0 となり並べ替えをしない。負値は `size_t` への変換後にプロファイル長で上限化され、通常は全項目が対象になる |
| `--peer-device < 1`、または `--expert-profile` なし | 読み取りなし | 該当なし | 該当なし |

対象件数 `at` が 0 のときは並べ替え処理を行いません。`at > 0` でも、同じブロックで読む `STRATA_PEER_HOT` の `std::atof` 結果 `f` が `0.0 < f < 1.0` を満たさなければ並べ替えません。`STRATA_PEER_HOT` が未設定なら `f=0.45` です。`STRATA_PEER_HOT` の値はこの文書の対象外ですが、この条件が `STRATA_PEER_HOT_AT` の効果を抑止します。`engine/src/program/generate.cpp:6762-6767`、`engine/sycl/src/program/generate.cpp:3796-3801`

## 有効になる条件

- `--expert-profile` が空でなく、プロファイルの読み込みに成功する必要があります。プロファイル未指定時は環境変数を読みません。`engine/src/program/generate.cpp:6747-6751`、`engine/sycl/src/program/generate.cpp:3781-3785`
- `--peer-device` が 1 以上のときだけ読みます。`--peer-device` は CLI 引数で、環境変数の値がこれを有効化したり上書きしたりはしません。`engine/src/program/generate.cpp:4205`、`engine/sycl/src/program/generate.cpp:2169`、`engine/src/program/generate.cpp:6762-6766`、`engine/sycl/src/program/generate.cpp:3796-3800`
- peer tier の起動にはさらに有効な `--expert-cache` とプロファイルが必要です。`--layer-split` または `--expert-cache-device1..3` と併用すると引数検証で終了します。`--peer-device` には見えている別 GPU も必要です。`engine/src/program/generate.cpp:5284-5291`、`engine/src/program/generate.cpp:10213-10222`、`engine/src/core/peer_experts.cpp:197-202`
- `--peer-slots` と peer GPU の空き VRAM は peer cache が実際に取れる件数を制限します。これはランキングの移動数とは別の制約です。`engine/src/program/generate.cpp:4207`、`engine/src/core/peer_experts.cpp:264-280`
- SYCL でもこの値を読む条件は同じですが、`PeerExperts::open` が `--peer-device: the second-GPU expert tier is not ported to SYCL yet` を返すため peer tier は利用できません。`engine/sycl/src/program/generate.cpp:5750-5759`、`engine/sycl/src/core/peer_experts.cpp:19-22`

## 実行時の詳細

CLI 引数の解析後、`--expert-profile` を読み込んだ起動時の初期化中に一度読みます。関数内 static などへの環境値の cache はありませんが、変換後の順位リストはその実行中に使われます。serve モードも同じ初期化経路を使うため、リクエストごとに環境を読み直す処理ではありません。`engine/src/program/generate.cpp:3670`、`engine/src/program/generate.cpp:4205-4212`、`engine/src/program/generate.cpp:6747-6785`、`engine/src/program/generate.cpp:18402-18404`

`r=0..at-1` の各順位について、`floor((r+1)f) > floor(rf)` となる項目を `moved`、それ以外を `keep` に分けます。`keep` の後に元の順位 `at` から `min(profile.size(), at + moved.size())` までを置き、その後に `moved` を置いて残りを続けます。これにより primary cache がランキング順に埋められた後、peer cache は primary が保持していない項目を順位順に選びます。primary cache の充填数は `--expert-cache` 等の cache 条件で決まり、peer cache は空き VRAM と `--peer-slots` でも制限されるため、環境変数だけで peer が保持する件数は決まりません。`engine/src/program/generate.cpp:6767-6782`、`engine/src/program/generate.cpp:9750-9763`、`engine/src/core/peer_experts.cpp:264-280`

CUDA/HIP では peer cache の初期化に失敗するとエラーを stderr に出して終了コード 1 を返します。プロファイルまたは cache がない場合は `--peer-device needs --expert-profile and the expert cache`、peer に空きがない場合は `peer experts: no room or no expert left for the peer` です。`engine/src/program/generate.cpp:10213-10222`、`engine/src/core/peer_experts.cpp:282`

## ログと測定値

並べ替えが実行された場合、stderr に次の形式で出ます（`f` と各件数は実行時の値です）。`at=0` または `f` が範囲外なら、この行は出ません。

```text
strata generate: STRATA_PEER_HOT %.2f: %zu of the first %zu ranked pairs moved behind rank %zu (the peer's)
```

CUDA/HIP の文字列出力は `engine/src/program/generate.cpp:6783-6784`、SYCL は `engine/sycl/src/program/generate.cpp:3817-3818` にあります。SYCL ではこの出力後に peer tier 未対応エラーになります。対象環境変数の測定値を説明する Strata 資料は確認できませんでした。

## 根拠

- `engine/src/program/generate.cpp:6747-6788` — プロファイル読み込み、peer-device 条件、環境値の変換、順位変更、ログ。
- `engine/sycl/src/program/generate.cpp:3781-3823` — SYCL 側の同じ処理。
- `engine/src/program/generate.cpp:9750-9808` — 変更後の順位を primary cache の充填順に使う。
- `engine/src/core/peer_experts.cpp:264-312` — primary にない順位項目を peer cache が選び、制約内で充填する。
- `engine/sycl/src/core/peer_experts.cpp:19-22` — SYCL peer tier の未対応エラー。
- `docs/SECOND_GPU.md:70-103`、`docs/A770_SPEED_SPEC.md:277-285` — peer tier の概要と SYCL 未対応に関する資料。環境変数の値判定はソースコードを根拠とした。
