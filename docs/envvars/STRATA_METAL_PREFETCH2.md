# `STRATA_METAL_PREFETCH2`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

Metal engine の SSD expert streaming で、現在層の FFN 入力から計算した2層先 router logits を使い、その層の expert を先読みする数を指定します。層 `l` の処理中に層 `l+2` の予測上位 expert を非緊急 I/O queue に投入し、後の層で必要になったときの読み込み待ちを減らすための設定です。既定値は `0`（無効）です。

この処理は `ExpertStream` が開かれたときだけ設定されます。Metal window が SSD streaming を選ばない場合、この変数は読み取られません。streaming の選択は `STRATA_METAL_STREAM` の明示値、またはモデルの常駐メモリ条件によります。根拠: `metal/src/engine/stream.cpp:33-40,157-159`, `metal/src/engine/window.cpp:451-458`。

## 値と判定

`env_int()` は環境変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で変換します。文字列全体の数値検証はしません。

| 値 | `pre_k2_` の結果 | 挙動 |
|---|---:|---|
| 未設定、空文字 | `0` | 2層先先読みなし |
| `0`、非数値文字列（例: `abc`） | `0` | 2層先先読みなし |
| 正の整数文字列（例: `1`, `12`, `12tail`） | 変換された整数 | 2層先の予測上位を先読み。実際の `K` は最大32 |
| 負の整数 | 負の整数 | `pre_k2_ > 0` の条件を満たさず無効 |

`atoi` のため、先頭空白や符号を含む数値接頭辞も変換されます。`ahead()` は `K` を `min(K, 32)` に制限します。したがって正の値を32より大きくしても、各 token の候補数は32を超えません。根拠: `metal/src/engine/stream.cpp:27-30,157-159,574-578`。

## 有効になる条件

- Metal engine が SSD expert streaming を使う必要があります。変数単独では streaming を有効化しません。
- `STRATA_METAL_PREFETCH` が `atoi` で正の値となり、1層先予測が有効である必要があります。window はこの条件で `predL_` を確保し、さらに `STRATA_METAL_PREFETCH2` の結果が正なら `predL2_` を確保します。1層先予測を無効にすると、2層先予測 logits も計算・先読みされません。
- `l + 2 < 48` の層に限られます。対象 window は層数48の Qwen3.8-Flash-Next geometry を要求します。
- prompt chunk（`T > 8`）では `at_layer()` が prompt 用の処理後に戻るため、2層先の `ahead()` を呼びません。2層先先読みは decode window の処理で使われます。

根拠: `metal/src/engine/window.cpp:435-442,620-629,888-897`; `metal/src/engine/stream.cpp:617-620,690-714`。

## 実行時の詳細

`ExpertStream::open()` が `STRATA_METAL_PREFETCH2` を一度読み、`pre_k2_` に保存します。window 初期化時に `ahead2() > 0` なら、`48 * MAXT * 512` 個の float を格納する `predL2_` buffer を確保します。各 layer の graph では、同じ層の FFN 入力 `XF_` に層 `l+2` の router weight を適用し、予測 logits をその buffer に書き込みます。layer cut に到達すると、`at_layer()` は層 `l+2` の logits を渡します。

`ahead()` は各 token の logits から上位 `K` expert を選び、複数 token に重複する expert をまとめ、expert の最大 logit 順に並べます。arena にない expert は victim slot を得られる範囲で非緊急 read-ahead queue に投入されます。空き slot がなく victim を得られないところで投入を止めます。後続層で予測が外れた未開始 read-ahead は破棄され、実際に必要になった queue 済み読み込みは urgent 扱いに昇格します。根拠: `metal/src/engine/window.cpp:304-306,620-629,888-896`; `metal/src/engine/stream.cpp:574-614,640-648,660-665,711-714`。

値は `ExpertStream::open()` 時に読み込まれ、その instance のフィールドに保持されます。実行中に環境を変更しても再読込されません。環境変数専用のログ出力は確認できません。stream arena の初期化ログには1層先の `read-ahead top` のみが出力され、2層先の値は表示されません（`metal/src/engine/stream.cpp:541-544`）。

## 根拠

- 変換 helper と設定: `metal/src/engine/stream.cpp:27-30,149-162`
- streaming engine の選択: `metal/src/engine/stream.cpp:33-40`; `metal/src/engine/window.cpp:451-458`
- buffer と logits 計算: `metal/src/engine/window.cpp:620-629,888-897`
- top-K 選択、統合、queue 登録: `metal/src/engine/stream.cpp:574-614`
- layer callback、prompt 分岐、先読み呼び出し: `metal/src/engine/stream.cpp:617-620,690-714`; `metal/src/engine/window.cpp:304-306`

`docs/DETAILS.md` と関連する設計資料に、この変数固有の値や測定条件の記載は見つかりませんでした。性能向上や予測精度については、この調査では主張しません。
