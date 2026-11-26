# `STRATA_PEER_HOT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--peer-device` 用に読み込んだ expert profile の先頭順位から、指定割合の組を primary GPU の cache 順の後ろへ移し、peer GPU が primary に入りきらなかった場合に先に選べるようにする割合 `f` です。値は profile の順位変更だけを行い、`--peer-device` 自体や cache を有効化しません。CUDA と HIP の共通 GPU engine `engine/src/program/generate.cpp`、および SYCL 移植 `engine/sycl/src/program/generate.cpp` に同じ順位変更処理があります（共通処理: `engine/src/program/generate.cpp:6757-6785`、SYCL: `engine/sycl/src/program/generate.cpp:3791-3819`）。共通 engine は CUDA / HIP のどちらかが有効な構成で組み込まれます（`engine/CMakeLists.txt:20-22,712-714`、`engine/cmake/strata_gpu_engine.cmake:1-8`）。

実際に peer cache を使うには `--peer-device N`、読み込み可能な `--expert-profile`、有効な expert cache が必要です。共通 GPU engine では peer cache が primary cache に未収容の組を順位順に選びます（`engine/src/program/generate.cpp:10211-10227`、`engine/src/core/peer_experts.cpp:264-282`）。したがって移動対象の順位は primary cache から後ろへ回り、peer の候補順位が上がります。`--peer-device` がない場合はこの環境変数を読みません。SYCL は peer tier を stub として実装しています。

## 値と判定

profile が空でない場合に限り、peer device が `1` 以上なら `std::getenv` で読みます。未設定時は `0.45` です。設定時は `std::atof` で浮動小数点数へ変換し、`0.0 < f && f < 1.0` のときだけ並べ替えます。文字列全体の消費確認、errno、有限値確認はありません。`atof` が数値として読めない文字列は通常 `0` 相当となり、条件を満たさず無効です。先頭空白を含む数値や数値の後ろに文字がある値も、数値 prefix が変換対象です。大文字小文字の比較はありません。

| 条件 | 未設定 | 有効になる値の例 | 並べ替えない値の例 |
|---|---|---|---|
| `--peer-device N`（N >= 1）、profile 非空 | `0.45` | `0.3`, `0.45`, `0.999`, `0.3tail` | 空文字、`0`, `1`, `-0.1`, `true`, `nan`, `inf` |
| peer device 未指定、または profile 空 | 読み取りなし | 該当なし | 変数が設定されていてもこの処理では参照されない |

有効値でも移動件数は `STRATA_PEER_HOT_AT` による先頭範囲と、profile の長さに依存します。`STRATA_PEER_HOT_AT` は未設定なら `8700`、設定時は `atoll` 後に profile 長で上限を取ります。空文字や数値 prefix を持たない文字列は `0` となり移動を止めます。負値は `size_t` に変換された後に profile 長で制限されるため、実質 profile 全体が対象です。実際の各 rank `r` の移動判定は `floor((r+1)f) > floor(rf)` に相当する整数 cast の比較です（共通 engine: `engine/src/program/generate.cpp:6763-6785`、SYCL: `engine/sycl/src/program/generate.cpp:3796-3819`）。`STRATA_PEER_HOT_AT` は同じブロックで同時に読み取られる関連変数です。

## 有効になる条件

- `--expert-profile` が空でなく、profile の読み込みに成功する必要があります。読み込み失敗時は `strata generate: <error>` を stderr に出して終了コード `1` で戻り、環境変数処理には到達しません（`engine/src/program/generate.cpp:6747-6751`、SYCL: `engine/sycl/src/program/generate.cpp:3780-3785`）。
- profile 読み込み後、`--peer-device N` が `N >= 1` のときだけ変数を評価します。未設定時の `0.45` もこの条件の下だけ適用されます（`engine/src/program/generate.cpp:6762-6767`、SYCL: `engine/sycl/src/program/generate.cpp:3796-3801`）。
- profile がある場合、`--expert-cache 0` はこの処理で `-1`（自動設定）に置き換えられます。peer 起動時点で cache が正数でない場合は上記の不足エラーになります。CLI は peer tier を有効化しますが、割合 `f` はこの環境変数（または未設定時の既定値）で決まります（`engine/src/program/generate.cpp:6753-6756,10213-10217`、SYCL: `engine/sycl/src/program/generate.cpp:3787-3790,5750-5754`）。
- peer device 使用時は profile、expert source、正数の cache が必要です。不足時は `strata generate: --peer-device needs --expert-profile and the expert cache` を stderr に出し、終了コード `1` で戻ります（`engine/src/program/generate.cpp:10213-10217`、SYCL: `engine/sycl/src/program/generate.cpp:5750-5754`）。
- `--peer-device` は `--layer-split` と `--expert-cache-device1..3` と併用できず、該当時は `strata generate: --peer-device cannot be combined with ...` を stderr に出して終了コード `2` で戻ります（`engine/src/program/generate.cpp:5284-5291`、SYCL: `engine/sycl/src/program/generate.cpp:2698-2705`）。
- CUDA / HIP 共通の peer 実装は `engine/src/core/peer_experts.cpp` にあります。SYCL は環境変数を使った順位変更とログの後、peer を開く段階で `--peer-device: the second-GPU expert tier is not ported to SYCL yet` を返して失敗します（`engine/sycl/src/core/peer_experts.cpp:19-23`）。この場合、並べ替えによる実行時の peer cache 効果はありません。

## 実行時の詳細

読み取りは `generate` の起動処理で profile をロードした直後です。両実装とも関数内 static cache ではなく、その箇所で一度 `getenv` / `atof` を実行します。並べ替えた `profile` はその後の primary cache の fill に使われ（`engine/src/program/generate.cpp:9749-9766`）、peer cache は primary が保持しない組を同じ順位順に走査して収容します（`engine/src/core/peer_experts.cpp:264-282`）。環境変数を読むのは起動時の一回なので、実行中にプロセス環境を変更してもその起動済み profile の順序には反映されません。serve もこの engine 初期化経路を通るため、リクエストごとの読み直しではありません。

並べ替えは、先頭 `at` 個を `keep` と `moved` に分け、元の順位 `at` 以降から `moved.size()` 個を primary の追加枠として先に取り、その後ろに `moved` を置きます。`at` は profile 長以下に clamp され、primary 側の追加位置 `fill` も profile 長以下です。よって peer に回す意図の組を primary が引き続き保持できる容量の場合もあり、最終的に peer が選ぶのは primary cache に入らなかった組だけです（`engine/src/program/generate.cpp:6767-6782`、`engine/src/core/peer_experts.cpp:272-280`）。

## ログと測定値

有効な `f` と `at > 0` なら、並べ替え直後に stderr へ次の形式で出ます（値と件数は実行時値）。

```text
strata generate: STRATA_PEER_HOT %.2f: %zu of the first %zu ranked pairs moved behind rank %zu (the peer's)
```

`f` が範囲外、`at == 0`、peer device なし、または profile が空の場合、この環境変数に関するログは出ません。CUDA / HIP で peer 初期化に成功すると続けて `peer GPU ...` の resident 数ログが出ます。peer 初期化が失敗すればそのエラーを stderr に出して終了コード `1` です（`engine/src/program/generate.cpp:6783-6785,10219-10227`）。SYCL では有効な割合なら移動ログが出た後、上記の未 port エラーを `strata generate: ...` 形式で出して終了コード `1` になります（`engine/sycl/src/program/generate.cpp:3817-3819`、`engine/sycl/src/core/peer_experts.cpp:19-23`）。

この環境変数の効果を定量化する測定値は、調査対象コードと関連資料から確認できませんでした。コードコメント中の測定に関する記述は測定条件を示していないため、ここでは結果として記載しません。

## 根拠

- `engine/src/program/generate.cpp:6747-6789` — profile 読み込み、既定値、値の変換・範囲判定・順位変更。
- `engine/sycl/src/program/generate.cpp:3780-3823` — SYCL 側の対応処理。
- `engine/src/program/generate.cpp:9749-9766,10211-10227` — primary profile fill と peer 起動条件、ログ。
- `engine/src/core/peer_experts.cpp:192-213,264-312` — CUDA / HIP 共通 peer tier の初期化と、primary 未収容組を順位順に選ぶ処理。
- `engine/sycl/src/core/peer_experts.cpp:19-23` — SYCL peer tier が未 port のため失敗する処理。
- `engine/src/program/generate.cpp:5284-5291`, `engine/sycl/src/program/generate.cpp:2698-2705` — peer と layer split / helper cache の併用制限。
- `engine/CMakeLists.txt:20-22,712-714`, `engine/cmake/strata_gpu_engine.cmake:1-8` — 共通 GPU engine が CUDA / HIP build に含まれる条件。
- `docs/INTEL.md:415-419` — SYCL peer tier が stub である旨。実際の値判定・処理は上記ソースコードを根拠とした。
