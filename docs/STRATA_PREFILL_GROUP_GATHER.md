# `STRATA_PREFILL_GROUP_GATHER`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリ自身が読む環境変数の挙動は対象外。

## 役割

長い prompt の streamed prefill で、native expert の MMQ 用重み取り込み（gather）を expert ごとに行う代わりに、最大16 expert のグループ単位でまとめます。対応経路では、コピー待ちをグループ末尾の一回にまとめ、グループの ring slot を一つの完了 event で再利用可能にします。MMQ 計算に使う group buffer の内容は、個別 gather と同じ配置になるよう実装されています。

CUDA 実装は `src/prefill/prefill.cpp`、SYCL 実装は `sycl/src/prefill/prefill.cpp` にあります。値の判定は関数内の `static const bool` で一度だけ行われ、最初に評価された後のプロセス内環境変更は反映されません。

## 値と判定

設定値は `std::atoi(v) != 0` で判定します。文字列全体の厳密な数値 parse や `1` との比較ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | 有効 |
| 空文字、数値として先頭を読めない文字列、`0` で始まる数値 | 無効（`atoi` の結果が 0） |
| `1`、`-1`、その他 `atoi` が 0 以外を返す文字列 | 有効 |

`atoi` は先頭の空白と符号を許し、数値部分の後ろに文字があっても変換できた整数を返します。したがって、たとえば ` 1x` は有効、`0x` は無効、`true` は無効です。大文字小文字の判定はありません。

根拠: `src/prefill/prefill.cpp:3830-3835`、`sycl/src/prefill/prefill.cpp:3895-3900`。

## 有効になる条件

環境値が有効でも、実際のグループ gather は次の条件を全て満たす場合に限られます。

- prefill が streamed walk を使う。共通判定では `m.ring > STAGE`、`T >= stream_all_min()`、expert source が存在することが必要です（`STAGE` は8）。`stream_all_min()` の既定値は1,024 tokens で、`STRATA_PREFILL_STREAM_MIN` または CPU share 用の内部設定により変わり得ます。
- その layer で MMQ が選択されている。
- expert layout が native。
- `MMQ_GROUP`（16）が `mmq::kGatherGroupMax` 以下。

この条件外では、この変数の値にかかわらず対象のグループ gather は使いません。通常の gather や別の expert 計算経路に進みます。native group gather 関数はポインタ・offset・size の16-byte alignmentも検査し、条件を満たさない場合は `false` を返します。その場合 CUDA caller はグループ内の expert を一つずつ `gather_native()` します。

根拠: `src/prefill/prefill.cpp:2341,3834-3835,3840-3858`、`include/strata/prefill/moe_mmq.hpp:89-101`、`src/prefill/moe_mmq.cu:409-430`。

## 実行時の詳細

グループ化が有効な streamed walk では、各 expert の device blob をグループ buffer の対応 slot に対応付け、MMQ group（最大16 expert）が埋まるか、その layer の最後に達した時点で flush します。flush は最後に投入された streamed copy の完了を待ち、可能なら一回の `gather_native_group()` launch で gate/up/down のデータをまとめて配置します。NVFP4 の tail と MMQ 用末尾 zero fill もこの処理に渡します。alignment 不適合時は expert ごとの gather に fallback します。

通常の streamed MMQ gather では expert ごとにコピー完了待ちと ring slot 解放 event を記録します。グループ経路では最後のコピーを待ってから gather し、グループの slot を最後の slot の完了 event に結び付けて一括で再利用します。router が選ばなかった expert の slot を返すときは、未完了 group を先に flush し、issuer に対してグループ分を過度に保持しない構造です。SYCL 側にも同じ環境判定とグループ化の分岐があります。

この設定自体による専用ログやエラー文はありません。ソースコメントは WDDM 下で expert ごとの wait/event が各約10 µsの GPU bubble を生み、32K prompt の NVFP4 pack で合計226 msだった例を記載しています。これはコメントに記載された条件の値であり、一般的な性能向上を保証する測定ではありません。`docs/DETAILS.md` にこの環境変数固有の説明や別の測定条件は見つかりませんでした。

根拠: `src/prefill/prefill.cpp:3823-3866,3870-3900,3977-4015`、`sycl/src/prefill/prefill.cpp:3888-3929,4020-4041,4201-4227`。
