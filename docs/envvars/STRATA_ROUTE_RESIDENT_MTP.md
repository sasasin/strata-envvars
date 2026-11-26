# `STRATA_ROUTE_RESIDENT_MTP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata serve` で MTP（multi-token prediction）draft を使うとき、MTP draft router に対して `STRATA_ROUTE_RESIDENT` と同じ常駐 expert 優先の補正を有効にする opt-in gate です。MTP が使う常駐表は verifier の最終層の行です。値が有効で補正が実行されると、MTP が提案する draft が変わることがあり、実装コメントも出力が変わると明記しています（`engine/src/program/generate.cpp:13229-13230`）。

これは通常の verifier 側補正を有効にする変数ではありません。MTP 用の設定だけであり、`STRATA_ROUTE_RESIDENT` の値（margin）が別途必要です。機能のセットは `strata serve` の初期化に置かれ、通常の `strata generate` 初期化にはこの変数の読み取りがありません（`engine/src/program/generate.cpp:12302-12314,13226-13241,24507-24508`）。

## 値と判定

値は `std::getenv` で取得され、設定されていることに加え、`std::atoi(value) != 0` のとき有効です。文字列全体の検証やエラー報告はありません。`atoi` が読み取る先頭の整数部分で判定されるため、空文字・整数変換できない文字列・`0`・`0abc` は無効、`1`・`-1`・`1abc` は有効です。先頭空白と符号は整数変換で扱われます（例: `  +1` は有効）。`true` / `false` は整数として始まらないため無効です。範囲確認や clamp はありません。数値範囲外の文字列については実装が検査していません（`engine/src/program/generate.cpp:13231-13232`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `strata serve` の MTP 補正 gate | 無効 | `atoi` の結果が非 0（例: `1`, `-1`, `1abc`） | `atoi` の結果が 0（例: 空文字, `0`, `0abc`, `true`） |

## 有効になる条件

- `strata serve` 経路で MTP が有効（`--mtp` の値が空でない）であること。設定は serve 初期化内の `use_mtp` を条件にします（`engine/src/program/generate.cpp:12302-12314,13231`）。
- レイヤー分割の `stages` が空であること。分割時はこの MTP 用 setter を呼びません（`engine/src/program/generate.cpp:13231`）。
- `thits.d_res` が存在すること。device residency table は profile と graphed hit path が成立し、capture 等の条件も満たす経路で確保・転送されます。具体的には `graph_hits` が hit function または zero-slot residency と非空 profile、pool 有効を要求し、device table の確保にはさらに capture 有効、token graph 有効、layer/half dump 無効が必要です（`engine/src/program/generate.cpp:10997-11016`）。これらの条件が満たされず `d_res` が null なら、この変数だけ設定しても効果はなく、理由ログも出ません。
- `STRATA_ROUTE_RESIDENT` が設定され、その `std::atof` 結果が `0.0f` より大きいこと。未設定時や空文字・数値に変換できない値などで margin が正にならなければ補正は設定されず、MTP 用有効ログも出ません。MTP gate 自体が非 0 でも、この margin 条件は別に必要です（`engine/src/program/generate.cpp:13231-13240`）。
- MTP router の実行時にも expert 数が 512、top-k が 10、margin が正であること。条件に合う場合だけ native resident router を呼びます（`engine/src/core/mtp.cpp:1432-1435`）。
- `STRATA_ROUTE_RESIDENT_RANKS` があれば `sscanf("%d-%d", ...)` で対象 rank の上下端を読み、なければ `6-9` を使います。この環境変数の値検査や rank の範囲 clamp はこの初期化箇所にはありません（`engine/src/program/generate.cpp:13234-13237`）。kernel は指定された rank から `hi` までを走査し、rank が 10 未満であることだけを上限側で確認します（`engine/src/kernels/cuda/native_router.cu:278-299`）。

## 実行時の詳細

環境変数は serve 起動中、verifier を用意する前に一度評価されます。3 つの環境変数の値はこの時点で読み、条件が揃い margin が正なら最終層の residency row、margin、rank 範囲を `mtp.set_route_resident(...)` に保存します。MTP router は draft の router/top-10 の後にこの設定を検査し、512 experts・top-k 10 の場合に補正 kernel を起動します（`engine/src/program/generate.cpp:13226-13241`; `engine/src/core/mtp.cpp:1420-1435`）。この変数自体に static cache はありませんが、読み取り後は setter の状態として MTP drafter に保持されるため、serve 実行中にプロセス環境を書き換えても再評価されません。

補正 kernel は選択済み top-10 の `lo..hi` rank を見ます。対象 rank の expert が非常駐なら、まだ選ばれていない常駐 expert のうち logit が最良のものを探し、元 expert との logit 差が margin 以下なら置き換えます。置換があった場合は選択 expert の logits から重みを再計算します（`engine/src/kernels/cuda/native_router.cu:253-256,278-319`）。これは MTP draft の router 結果を変える処理です。生成結果の最終採用は speculative verify 経路が引き続き担当します（serve の MTP draft と verify 窓: `engine/src/program/generate.cpp:23141-23144`）。

## ログと測定値

設定が実際に MTP drafter へ渡された場合、stderr に次の行を出します（layer は最終層番号、margin と ranks は読み取った値です）。有効な gate でも他の条件が不足する場合や margin が正でない場合、この行は出ません（`engine/src/program/generate.cpp:13231-13240`）。

```text
strata generate: STRATA_ROUTE_RESIDENT_MTP: the MTP draft's router is biased toward layer <N>'s resident experts (margin <M>, ranks <LO>-<HI>; experimental)
```

MTP route kernel の起動が例外を返すと `MtpDrafter::draft` は `mtp route-resident: ...` を error に設定して失敗します。serve loop は `ERR <error>` を stdout に出し、終了コード 1 で戻ります（`engine/src/core/mtp.cpp:1432-1435`; `engine/src/program/generate.cpp:23141-23144,23185-23187`）。ソース内にこの変数固有の測定値はありません。

## 根拠

- `engine/src/program/generate.cpp:13226-13241` — gate、依存変数、単一段経路、最終層 row の設定、stderr ログ。
- `engine/src/program/generate.cpp:10997-11016` — device residency table が作られる条件。
- `engine/include/strata/core/mtp.hpp:60-65` — MTP drafter に resident row と設定値を保持する setter。
- `engine/src/core/mtp.cpp:1420-1435` — MTP router 後の補正実行条件と失敗経路。
- `engine/src/kernels/cuda/native_router.cu:253-256,278-328` — resident expert の差し替え、margin 判定、weight 再計算、kernel 起動エラー。
- `engine/src/program/generate.cpp:23141-23144,23185-23187` — serve loop の MTP draft 呼び出しとエラー表示・終了。
