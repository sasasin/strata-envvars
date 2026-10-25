# `STRATA_VERIFY_NODES`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリ・driver の環境変数動作は対象外。

## 役割

Verifier がキャプチャした GPU window graph のノード構成を stderr に出す診断用スイッチです。CUDA ではノード種別とカーネル名（取得可能な CUDA Runtime では名前）、CUDA 12.3 以降では graph edge の数と programmatic dependency を出します。HIP では同様のノード集計に加え、値が 2 以上ならグラフ順の先頭ノード名も出します。SYCL では通常の window graph のノード集計と、分割キャプチャ時の segment 数を出します。MTP drafter の CUDA/HIP graph にも集計ログを出します。

これは graph の記録内容や実行計画を変更せず、診断ログだけを追加します。環境変数は graph capture 時に調べられます。すでに実行可能 graph がキャッシュされている場合、`capture()` は早期 return するため、その graph について改めて一覧を出しません。

## 値と判定

| 経路 | unset | 設定時の判定と出力 |
|---|---|---|
| CUDA Verifier（Metal を除く） | 一覧を出さない | 値の内容に関係なく、設定されていれば graph のノード集計を出す。CUDA Runtime 12.3 以降は edge / programmatic dependency 情報も出す |
| HIP Verifier | 一覧を出さない | 値の内容に関係なくノード集計を出す。さらに `std::atoi(value) >= 2` なら graph 順の先頭最大 400 ノード名を出す |
| SYCL Verifier | 一覧を出さない | 値の内容に関係なく、通常の graph ならノード集計、分割 capture なら segment 数を出す |
| MTP drafter（Metal を除く CUDA/HIP） | 一覧を出さない | 値の内容に関係なく、MTP graph のノード集計を出す |

設定有無を調べる箇所は `getenv(...) != nullptr` なので、空文字も設定扱いで集計を有効にします。文字列が `1` である必要はありません。HIP の詳細一覧だけは `atoi` で数値化し、変換結果が 2 以上かを判定します。`atoi` は文字列全体の厳密な数値 parse ではないため、先頭の空白や符号の後の数字を読み、数字以降の文字は無視します（例: `2tail` は 2）。数値に変換できない文字列や空文字は 0 相当となり、詳細一覧は出ません。負数も出ません。

## 有効になる条件

- CUDA Verifier の一覧は `STRATA_USE_HIP` と `STRATA_GPU_METAL` が定義されないビルドでのみコンパイルされます。CUDA 12.3 未満では kernel function 名の取得と edge 情報は出ず、型番号または種別名を使った集計にとどまります。
- HIP Verifier では graph capture が成功した後に一覧を作ります。Windows では kernel 名取得関数を `amdhip64_7.dll` から検索し、関数が取得できない場合は型番号を表示します。
- SYCL の stepped mode で `g_stepped && !ar_on()` かつ `STRATA_VERIFY_EAGER` が未設定なら、通常 graph ではなく segment capture に進み、segment 数のみを出します。`STRATA_VERIFY_EAGER` が設定されている経路は graph capture を行わないため、graph ノード一覧はありません。
- MTP の一覧関数は graph pointer が null なら出力しません。Metal では一覧を出さず、CUDA/HIP で MTP graph capture が成功したときに出力します。
- 変数を設定しても、Verifier/MTP graph capture 自体を使用しない経路には graph 一覧はありません。

## 実行時の詳細

CUDA Verifier は capture を終えた graph から全ノードを取得し、ノード種別名ごとに数えて降順で表示します。最大 40 種類を出し、行頭は `strata verify: the %d-token window graph has %zu nodes:` です。CUDA Runtime 12.3 以降では edge を取得し、programmatic edge 数と、そのうち kernel-to-kernel でない数も表示します。edge query が失敗した場合は ` (the edge query failed)` が付きます。

HIP Verifier は graph のノードを集計して最大 80 種類を表示します。値の `atoi` 結果が 2 以上ならノードを graph 順にも列挙します。最大 400 件で、各名は最大 110 文字に切り詰められます。Windows 以外では `hipKernelNameRefByPtr`、Windows では DLL から取得した同関数を使い、kernel 名が得られない場合は `typeN` の形式を使います。

SYCL Verifier は通常の graph についてノード種別を集計しますが、kernel 名は introspection できないため `kernel` として数えます。最大 40 種類を表示します。stepped mode の segment capture は graph 単位の一覧ではなく、`strata verify: the %d-token window as %zu graph segments` を出します。

MTP の `finish_capture()` は capture・instantiate が成功した graph を `mtp_list_nodes()` に渡します。CUDA では kernel を `kernel` として数え、HIP では取得可能な kernel 名を使います。集計は `strata mtp: the %s graph has %zu nodes:` から stderr に出ます。Metal では関数がログ出力を省略します。

各経路とも値は graph capture ごとに `getenv` で確認され、static cache されません。したがって、capture 前にプロセス環境の値が変われば次の capture に反映されます。通常、一度キャプチャ済みの Verifier graph や MTP graph は再利用されるため、その再利用時には capture に伴うログは再出力されません。

## 根拠

- `src/core/verify.cpp:1881-1906,1908-1945,1947-2003`: CUDA/HIP Verifier の capture 成功後の一覧、値判定、HIP の `atoi >= 2`、CUDA edge 診断。
- `src/core/verify.cpp:2005-2008`: 一覧処理後に実行可能 graph を生成・upload する流れ。
- `sycl/src/core/verify.cpp:1677-1719`: SYCL stepped segment capture と segment 数ログ。
- `sycl/src/core/verify.cpp:1726-1793`: SYCL eager/通常 capture 分岐と graph ノード集計。
- `src/core/mtp.cpp:815-863,1225-1243`: MTP の一覧 helper と capture 成功後の呼び出し。
- `docs/DETAILS.md` および `docs/INTEL.md` には、この環境変数の挙動を直接説明する記述は見つかりませんでした。
